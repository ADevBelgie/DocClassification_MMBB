"""
main.py

Serves as the entry point of the file renaming application, preparing failed files
for reprocessing by ContractScanner_MMBB. This script handles database interactions,
file renaming, and status updates while maintaining consistent logging and error handling.
"""
import os
import logging
from datetime import datetime
import time
import threading
import json
from .sql_utils import (
    connect_to_azure_db, 
    get_failed_unprocessed_records,
    update_renamed_record,
    update_rename_failed,
    check_duplicate_filename
)
from .file_utils import find_file_path, rename_file, validate_new_filename
from .api_client import (
    check_image_quality,
    process_file_for_api,
    communicate_with_api,
)

# Global lock for thread safety
lock = threading.Lock()

class LockError(Exception):
    pass

def acquire_lock(lock_file):
    with lock:
        if os.path.exists(lock_file):
            return False
        try:
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except IOError:
            return False

def release_lock(lock_file):
    with lock:
        try:
            os.remove(lock_file)
        except OSError:
            pass

def load_config():
    """
    Loads the application configuration from a JSON file.
    """
    with open('data/config.json', 'r') as config_file:
        return json.load(config_file)

def setup_logging(log_directory):
    """
    Configures logging with daily rotation.
    """
    os.makedirs(log_directory, exist_ok=True)
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_directory, f"doc_classification_{current_date}.log")
    
    file_handler = logging.FileHandler(log_file)
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info(f"New logging session started at {datetime.now()}")

def generate_new_filename(original_filename):
    """
    Generates a valid filename for ContractScanner_MMBB processing.
    """
    base_name = os.path.splitext(original_filename)[0]
    extension = os.path.splitext(original_filename)[1]
    
    # Add 'Contract_Payment' if not present
    if 'contract' not in base_name.lower() or 'payment' not in base_name.lower():
        new_name = f"Contract_Payment_{base_name}{extension}"
    else:
        new_name = original_filename

    return new_name

def process_failed_record(conn, record):
    """
    Processes a single failed record, attempting to rename and update its status.
    """
    try:
        logging.info(f"Processing record {record.contract_payments_id}")
        
        # First verify/find the file location
        current_path = record.full_file_path
        if not os.path.exists(current_path):
            logging.info(f"File not found at {current_path}, searching for new location...")
            found_path = find_file_path(record.deal_name, record.file_name)
            if not found_path:
                error_msg = "File not found in any location"
                logging.error(error_msg)
                update_rename_failed(conn, record.contract_payments_id, error_msg)
                return
            current_path = found_path

        # Generate new filename
        new_filename = generate_new_filename(record.file_name)
        
        # Validate new filename
        is_valid, error_msg = validate_new_filename(new_filename)
        if not is_valid:
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        # Check for duplicates
        if check_duplicate_filename(conn, new_filename, record.deal_id):
            error_msg = f"Duplicate filename would be created: {new_filename}"
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        # Attempt rename
        success, result = rename_file(current_path, new_filename)
        if success:
            # Update database with new filename and path
            update_renamed_record(conn, record.contract_payments_id, new_filename, result)
            logging.info(f"Successfully processed record {record.contract_payments_id}")
        else:
            update_rename_failed(conn, record.contract_payments_id, result)
            logging.error(f"Failed to rename file for record {record.contract_payments_id}: {result}")

    except Exception as e:
        error_msg = f"Error processing record {record.contract_payments_id}: {str(e)}"
        logging.error(error_msg)
        update_rename_failed(conn, record.contract_payments_id, str(e))

def main(lock_file='doc_classification.lock'):
    """
    Main function that orchestrates the file renaming process.
    """
    if not acquire_lock(lock_file):
        print("Another instance is already running. Exiting.")
        raise LockError("Failed to acquire lock")

    try:
        config = load_config()
        setup_logging(config['log_directory'])
        
        conn = connect_to_azure_db(config)
        try:
            failed_records = get_failed_unprocessed_records(conn)
            
            if not failed_records:
                logging.info("No failed records to process.")
                return
                
            logging.info(f"Found {len(failed_records)} failed records to process.")
            
            for record in failed_records:
                process_failed_record(conn, record)
                
        finally:
            conn.close()
            logging.info("Database connection closed.")
            
        logging.info("Processing completed successfully.")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise
    finally:
        release_lock(lock_file)

if __name__ == "__main__":
    main()