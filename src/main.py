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
from .api_client import classify_file

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

def process_failed_record(conn, record):
    """
    Processes a single failed record, attempting to classify and rename it.
    """
    try:
        logging.info(f"Processing record {record.contract_payments_id}")

        # Step 1: Define constants
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.pdf'}
        valid_classifications = {
            'Rental_Contract', 'Mortgage_Contract', 'Contract_Payment',
            'Teleworking_Agreement', 'Repayment_Table', 'Unclassified', 'Telework_Agreement', 'Homecostrenewal'
        }
        non_modifiable_files = [
        "housingrefundrequest",
        "housingcostrefundrequest",
        "housingrefundmodification",
        "yearrenewal",
        "mmbbform"
        ]

        # Step 2: Basic file validation
        file_name = record.file_name
        extension = os.path.splitext(file_name)[1].lower()
        
        # Step 3: Check if file has valid extension
        if extension not in allowed_extensions:
            error_msg = "Unsupported file type"
            logging.info(f"Skipping {file_name}: {error_msg}")
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        # Step 4: Check if file is non-modifiable - using original logic
        normalized_filename = file_name.lower().replace("_", "").replace(" ", "")
        is_non_modifiable = any(non_modifiable_file.lower() in normalized_filename 
                               for non_modifiable_file in non_modifiable_files)
        
        if is_non_modifiable:
            error_msg = "Not allowed to change - protected filename"
            logging.info(f"Skipping {file_name}: {error_msg}")
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        # Step 5: Check if already classified
        if any(classification.lower() in file_name.lower() 
               for classification in valid_classifications):
            error_msg = "Already classified"
            logging.info(f"Skipping {file_name}: {error_msg}")
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        # Step 6: Verify file location
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

        # Step 7: Process file through Claude API
        save_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                    "..", "data", "saved_images")
        os.makedirs(save_directory, exist_ok=True)
        
        logging.info(f"Classifying file: {current_path}")
        classification_result, api_response = classify_file(current_path)
        
        # Step 8: Handle classification results
        if classification_result == "Unclassified - Poor image quality":
            logging.info(f"File {file_name} classified as Unclassified due to poor image quality.")
            classification_result = "Unclassified"
        elif not classification_result or classification_result not in valid_classifications:
            error_msg = f"Invalid or no classification received: {api_response}"
            logging.error(f"Skipping {file_name}: {error_msg}")
            update_rename_failed(conn, record.contract_payments_id, error_msg)
            return

        logging.info(f"File classified as: {classification_result}")

        # Step 9: Rename file using classification
        success, result = rename_file(current_path, classification_result)
        if success:
            new_filename = os.path.basename(result)
            update_renamed_record(conn, record.contract_payments_id, new_filename, result)
            logging.info(f"Successfully processed record {record.contract_payments_id}")
        else:
            update_rename_failed(conn, record.contract_payments_id, result)
            logging.error(f"Failed to rename file for record {record.contract_payments_id}: {result}")

    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error processing record {record.contract_payments_id}: {error_msg}")
        update_rename_failed(conn, record.contract_payments_id, error_msg)

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
                time.sleep(1)  # Small delay between records
                
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