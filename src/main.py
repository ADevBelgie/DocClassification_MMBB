"""
main.py

Serves as the entry point of the file classification and renaming application, coordinating
the main functional components from api_client.py and file_utils.py. This script handles
user interaction, setups logging, and manages file processing workflows, directing the flow
of operations based on the configurations and user inputs. It handles the logging of processing
results and directs file renaming based on API analyses.
"""
import os
import logging
import datetime
from file_utils import find_deal_folders
from api_client import classify_file
import json

def load_config():
    """
    Loads the application configuration from a JSON file.

    Returns:
        dict: Configuration dictionary.
    """
    with open('data/config.json', 'r') as config_file:
        return json.load(config_file)

def setup_logging(log_directory):
    """
    Configures the logging for both file and console outputs.
    
    Parameters:
        log_directory (str): The directory where the log files are stored.
        
    This setup logs all critical operations, providing a dual logging mechanism for both file and console to assist during development and troubleshooting.
    """
    log_filename = datetime.datetime.now().strftime("Logs_%Y%m%d%H%M%S.log")
    log_path = os.path.join(log_directory, log_filename)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(log_path), logging.StreamHandler()])

def rename_file(original_path, classification):
    """
    Renames a file based on the classification received from the API.

    Args:
        original_path (str): The full path of the original file.
        classification (str): Classification string that modifies the filename.

    Returns: 
        str: The new file path after renaming.

    This function modifies the original filename by appending the classification result to its name before its extension. It also ensures that the new filename is unique within its directory by appending a counter if necessary.
    """
    try:
        directory, old_file_name = os.path.split(original_path)
        _, ext = os.path.splitext(old_file_name)
        new_name = f"{classification}{ext}"
        new_path = os.path.join(directory, new_name)
        counter = 1
        # Ensure the new filename is unique
        while os.path.exists(new_path):
            new_path = os.path.join(directory, f"{classification} ({counter}){ext}")
            counter += 1

        os.rename(original_path, new_path)
        return new_path
    except OSError as e:
        logging.error(f"Error renaming file {original_path}: {str(e)}")
        return original_path  # Return original path if renaming fails

def update_file_status(file_path, status, deals_found_path, new_filename=None):
    """
    Updates the log of file processing statuses, noting changes or appending new entries.

    Args:
        file_path (str): Path of the file being updated.
        status (str): The current status of the file ("Completed", "Skipped", etc.).
        deals_found_path (str): Path to the log file where statuses are recorded.
        new_filename (str, optional): The new filename if the file was renamed.

    This function logs the status of a file processing task by either updating existing entries or appending new ones to a dedicated log file.
    """
    try:
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        updated = False
        with open(deals_found_path, "r+") as file:
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                if file_path in line:
                    # If there's a new filename and the status is "Completed", log the new filename
                    if new_filename and status == "Completed":
                        file.write(f"  {filename} - {status} -> {new_filename}\n")
                    else:
                        file.write(f"  {filename} - {status}\n")
                    updated = True
                else:
                    file.write(line)
            
            if not updated:
                # Append new file status, indented under its directory
                if new_filename and status == "Completed":
                    file.write(f"  {filename} - {status} -> {new_filename}\n")
                else:
                    file.write(f"  {filename} - {status}\n")
            file.truncate()  # Important to avoid leaving trailing parts of old data
    except Exception as e:
        logging.error(f"Failed to update status for {file_path}: {e}")

def update_deal_status(deal_path, status, deals_found_path):
    """
    Updates or appends the status of a deal directory in the log file.

    Args:
        deal_path (str): Path of the deal directory.
        status (str): Status to log ("Completed", "Empty").
        deals_found_path (str): Path to the log file where deal statuses are recorded.

    This function manages the status updates of entire directories in the deal-focused log, ensuring that processing milestones are properly recorded.
    """
    try:
        updated = False
        with open(deals_found_path, "r+") as file:
            lines = file.readlines()
            file.seek(0)
            found_deal = False
            for line in lines:
                if deal_path in line and not any(char in line.strip()[len(deal_path):] for char in "\\/"):
                    if line.strip().startswith(deal_path):
                        file.write(f"{deal_path} - {status}\n")
                        found_deal = True
                        updated = True
                    else:
                        file.write(line)
                else:
                    file.write(line)

            if not updated and not found_deal:
                # If the deal wasn't previously mentioned, append it
                file.write(f"{deal_path} - {status}\n")
            file.truncate()
    except Exception as e:
        logging.error(f"Failed to update deal status for {deal_path}: {e}")

def process_files(files, deals_found_path):
    """
    Processes a list of files for classification and optional renaming based on content analysis provided by the API.

    Args:
        files (list of str): List of file paths to process.
        deals_found_path (str): Path to the file where processing status is logged.

    This function filters files by extension and existing classification, updates their status,
    and handles their renaming based on API responses. It logs all significant actions to facilitate tracking and review.
    """
    logging.info(f"Process files: {files}")
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.pdf'}
    # Use lowercase for all valid classifications for case-insensitive comparison
    valid_classifications = {'rental_contract', 'mortgage_contract', 'contract_payment', 'teleworking_agreement', 'repayment_table', 'unclassified'}

    for file_path in files:
        file_name = os.path.basename(file_path)
        extension = os.path.splitext(file_name)[1].lower()

        # Check if file is already classified
        already_classified = any(classification in file_name.lower() for classification in valid_classifications)

        if already_classified or file_name in ["Housing_Refund_Request.pdf", "Housing_Refund_Modification.pdf"] or extension not in allowed_extensions:
            reason = "Already classified" if already_classified else (
                "Not allowed to change" if file_name in ["Housing_Refund_Request.pdf", "Housing_Refund_Modification.pdf"] else "Unsupported file type"
            )
            update_file_status(file_path, f"Skipped - {reason}", deals_found_path)
            logging.info(f"Skipped processing {file_path}: {reason}")
            continue

        classification, api_response = classify_file(file_path)
        # Convert classification to lowercase for case-insensitive comparison
        if classification == 'Unclassified - Poor image quality' and api_response is None:
            logging.info(f"File {file_path} classified as Unclassified because of poor image quality before sending to AI classification.")
            classification = 'Unclassified'
        elif classification is None or classification.lower() not in valid_classifications:
            status = "Skipped - Invalid or no classification"
            update_file_status(file_path, status, deals_found_path)
            logging.error(f"Skipped processing {file_path} due to invalid or missing classification: {api_response}")
            continue

        # Rename file if classification was successful
        new_file_path = rename_file(file_path, classification)
        new_filename = os.path.basename(new_file_path)
        update_file_status(file_path, "Completed", deals_found_path, new_filename)
        # Log renamed files
        if new_file_path != file_path:
            logging.info(f"File renamed: {new_file_path}")

def main():
    """
    The main function that orchestrates the file processing workflow.

    It loads the configuration, sets up logging, finds deal folders, and processes files in batches
    based on user input. The function keeps track of the processing status in the Deals_Found.txt file
    and allows users to continue processing until all deals are completed or the user chooses to stop.
    """
    try:    
        config = load_config()
        setup_logging(config['log_directory'])
        base_path = config['base_path']
        base_path_accounts = config['base_path_accounts']
        deals_found_path = config['deals_found']
        

        deals_info = find_deal_folders(base_path)
        accounts_deals_info = find_deal_folders(base_path_accounts, is_account=True)
        # Merge deals from base_path and base_path_accounts
        deals_info.update(accounts_deals_info)

        # Write initial deal information to Deals_Found.txt
        with open(deals_found_path, 'w') as file:
            for deal, files in deals_info.items():
                file.write(f"{deal}\n")
                for f in files:
                    file.write(f"  {f}\n")

        total_deals = len(deals_info)
        print(f"Total number of deals found: {total_deals}")

        while total_deals > 0:
            number_to_process = int(input(f"Enter the number of deals you want to process (up to {total_deals}): "))
            number_to_process = min(number_to_process, total_deals)

            deals_to_process = list(deals_info.keys())[:number_to_process]
            empty_deals = []

            for deal in deals_to_process:
                if deals_info[deal]:
                    process_files(deals_info[deal], deals_found_path)
                else:
                    logging.info(f"No files found in the deal directory: {deal}")
                    empty_deals.append(deal)

            # Mark all processed deals as completed and remove them from deals_info
            for deal in deals_to_process:
                status = "Empty" if deal in empty_deals else "Completed"
                update_deal_status(deal, status, deals_found_path)
                del deals_info[deal]  # Remove the deal from the list of available deals

            # Adjust the total deals left to process
            total_deals = len(deals_info)

            if total_deals > 0:
                continue_processing = input("Would you like to process more deals? (yes/no): ")
                if continue_processing.lower() != 'yes':
                    break

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()
