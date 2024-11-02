import logging
from azure.identity import DefaultAzureCredential
import pyodbc
from datetime import datetime

def connect_to_azure_db(config):
    """
    Establishes connection to Azure SQL database using managed identity.
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        
        conn_str = (
            f'Driver={{ODBC Driver 18 for SQL Server}};'
            f'Server=tcp:{config["azure_sql_server"]}.database.windows.net,1433;'
            f'Database={config["azure_sql_database"]};'
            'Encrypt=Yes;TrustServerCertificate=No;'
            'Connection Timeout=30;'
            'Authentication=ActiveDirectoryMsi;'
        )
        
        conn = pyodbc.connect(conn_str)
        logging.info(f"Successfully connected to {config['azure_sql_database']} on {config['azure_sql_server']}")
        return conn
    except pyodbc.Error as e:
        logging.error(f"ODBC Error: {e}")
        logging.error(f"Error details: {e.args[1] if len(e.args) > 1 else 'No additional details'}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise

def get_failed_unprocessed_records(conn):
    """
    Retrieves records that failed due to file pattern issues and haven't been renamed.
    
    Args:
        conn: Database connection object
    
    Returns:
        List of records with status 'Failed' and has_been_renamed = false
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT TOP 50 *
            FROM contract_payments
            WHERE status = 'Failed'
            AND has_been_renamed = 0
            AND failure_reason LIKE 'File pattern does not match%'
            AND (
                deal_name LIKE '% - Housing Cost'
                OR deal_name LIKE '% - Home rent'
                OR deal_name LIKE '% - Home Mortgage Interest'
            )
            ORDER BY contract_payments_id
        """)
        logging.info("Fetching failed records with housing-related deal patterns")
        return cursor.fetchall()
    finally:
        cursor.close()

def update_renamed_record(conn, payment_id, new_file_name, new_file_path):
    """
    Updates a record after successful file renaming.
    
    Args:
        conn: Database connection object
        payment_id: ID of the payment record
        new_file_name: New name of the file
        new_file_path: New full path of the file
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        update_fields = {
            'file_name': new_file_name,
            'full_file_path': new_file_path,
            'status': 'New_DocClassification',  # Reset to New for ContractScanner to process
            'has_been_renamed': True,
            'last_updated': datetime.now(),
            'failure_reason': None  # Clear the failure reason
        }
        
        # Construct the SQL query using parameterization
        fields = ', '.join([f"{k} = ?" for k in update_fields.keys()])
        sql = f"UPDATE contract_payments SET {fields} WHERE contract_payments_id = ?"
        
        # Prepare the values for the SQL query
        values = list(update_fields.values()) + [payment_id]
        
        cursor.execute(sql, values)
        conn.commit()
        logging.info(f"Successfully updated renamed record {payment_id} with new file name: {new_file_name}")
    
    except pyodbc.Error as pe:
        conn.rollback()
        error_state = pe.args[1] if len(pe.args) > 1 else "Unknown"
        logging.error(f"Database error updating renamed record {payment_id}: {str(pe)}. Error state: {error_state}")
        raise
    
    except Exception as e:
        conn.rollback()
        logging.error(f"Unexpected error updating renamed record {payment_id}: {str(e)}")
        raise
    
    finally:
        if cursor:
            cursor.close()

def update_rename_failed(conn, payment_id, error_message):
    """
    Updates a record when renaming operation fails.
    Ensures the error message fits within the database column limits.
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        # Get the actual column size (optional, could be hardcoded based on your schema)
        cursor.execute("""
            SELECT CHARACTER_MAXIMUM_LENGTH 
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'contract_payments' 
            AND COLUMN_NAME = 'failure_reason'
        """)
        max_length = cursor.fetchone()[0] or 200  # Default to 200 if NULL
        
        # Prepare the error message to fit in the column
        message_prefix = "Rename operation failed: "
        available_length = max_length - len(message_prefix)
        truncated_message = (error_message[:available_length] 
                           if len(error_message) > available_length 
                           else error_message)
        final_message = message_prefix + truncated_message
        
        update_fields = {
            'has_been_renamed': True,  # Mark as processed even though it failed
            'last_updated': datetime.now(),
            'failure_reason': final_message
        }
        
        fields = ', '.join([f"{k} = ?" for k in update_fields.keys()])
        sql = f"UPDATE contract_payments SET {fields} WHERE contract_payments_id = ?"
        
        values = list(update_fields.values()) + [payment_id]
        
        cursor.execute(sql, values)
        conn.commit()
        logging.info(f"Updated failure reason for record {payment_id}")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error updating rename failure for record {payment_id}: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()

def check_duplicate_filename(conn, new_file_name, deal_id):
    """
    Checks if a filename already exists within the same deal.
    
    Args:
        conn: Database connection object
        new_file_name: Proposed new file name
        deal_id: ID of the deal
        
    Returns:
        bool: True if filename exists, False otherwise
    """
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM contract_payments
            WHERE file_name = ? AND deal_id = ?
        """, (new_file_name, deal_id))
        
        count = cursor.fetchone()[0]
        return count > 0
    
    finally:
        if cursor:
            cursor.close()