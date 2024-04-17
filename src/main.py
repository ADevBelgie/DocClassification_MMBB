import os
import logging
import datetime
from file_utils import find_ambiguous_filenames, write_to_file
from api_client import classify_file
import json

def load_config():
    with open('data/config.json', 'r') as config_file:
        return json.load(config_file)

def setup_logging(log_directory):
    log_filename = datetime.datetime.now().strftime("Logs_%Y%m%d%H%M%S.log")
    log_path = os.path.join(log_directory, log_filename)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(log_path), logging.StreamHandler()])

def rename_file(original_path, classification):
    try:
        directory, old_file_name = os.path.split(original_path)
        _, ext = os.path.splitext(old_file_name)
        deal_number = directory.split('\\')[-1].split(' ')[0]
        new_name = f"{deal_number} - {classification}{ext}" if classification != "Unclassified" else old_file_name

        new_path = os.path.join(directory, new_name)
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(directory, f"{deal_number} - {classification} ({counter}){ext}")
            counter += 1

        os.rename(original_path, new_path)
        return new_path
    except OSError as e:
        logging.error(f"Error renaming file {original_path}: {str(e)}")
        return original_path  # Return original path if renaming fails


def update_status(file_path, status):
    """
    Updates the status of file processing in the Ambiguous_file_names.txt.
    """
    # Read the current contents of the file
    with open("data/Ambiguous_file_names.txt", "r") as file:
        lines = file.readlines()

    # Update the status in the correct line
    with open("data/Ambiguous_file_names.txt", "w") as file:
        updated = False
        for line in lines:
            if file_path in line:
                line = line.strip() + f" - {status}\n"
                updated = True
            file.write(line)
        
        # If the file was not in the list, add it (safeguard)
        if not updated:
            file.write(f"{file_path} - {status}\n")

def process_files(files):
    changed_files_log = "data/Changed_files.txt"
    changed_files = []
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.pdf'}
    # Use lowercase for all valid classifications for case-insensitive comparison
    valid_classifications = {'rental contract', 'mortgage contract', 'contract payment', 'teleworking agreement', 'unclassified'}

    for file_path in files:
        file_name = os.path.basename(file_path)
        extension = os.path.splitext(file_name)[1].lower()

        # Check if file is already classified
        already_classified = any(classification in file_name.lower() for classification in valid_classifications)

        if already_classified or file_name in ["Housing_Refund_Request.pdf", "Housing_Refund_Modification.pdf"] or extension not in allowed_extensions:
            reason = "Already classified" if already_classified else (
                "Not allowed to change" if file_name in ["Housing_Refund_Request.pdf", "Housing_Refund_Modification.pdf"] else "Unsupported file type"
            )
            update_status(file_path, f"Skipped - {reason}")
            logging.info(f"Skipped processing {file_path}: {reason}")
            continue

        # Proceed with classification and renaming
        proceed = input(f"Ready to classify and possibly rename {file_path}? (yes/no): ")
        if proceed.lower() == 'yes':
            classification, api_response = classify_file(file_path)
            # Convert classification to lowercase for case-insensitive comparison
            if classification is None or classification.lower() not in valid_classifications:
                status = "Skipped - Invalid or no classification"
                update_status(file_path, status)
                logging.error(f"Skipped processing {file_path} due to invalid or missing classification: {api_response}")
                continue

            # Rename file if classification was successful
            new_file_path = rename_file(file_path, classification)
            if new_file_path != file_path:  # Only update if the file was renamed
                changed_files.append(f"{file_path} -> {new_file_path}")
                update_status(file_path, "Completed")
                write_to_file(changed_files, changed_files_log)
                logging.info(f"File renamed and logged: {os.path.join(os.path.basename(os.path.dirname(file_path)), os.path.basename(file_path))} -> {os.path.join(os.path.basename(os.path.dirname(new_file_path)), os.path.basename(new_file_path))}")
        else:
            update_status(file_path, "Skipped by user")

def main():
    config = load_config()
    setup_logging(config['log_directory'])
    logging.info("Starting the file name adjuster program.")

    # Define the base path to the network drive location (update this as necessary)
    base_path = config['base_path']
    ambiguous_file_path = config['ambiguous_file_log']

    # Find all ambiguous files and log them
    ambiguous_files = find_ambiguous_filenames(base_path)
    if ambiguous_files:
        write_to_file(ambiguous_files, ambiguous_file_path)
        logging.info(f"Logged {len(ambiguous_files)} ambiguous files to {ambiguous_file_path}.")
    else:
        logging.info("No ambiguous files found.")

    # User confirmation to proceed
    proceed = input("Found ambiguous files. Would you like to proceed with renaming? (yes/no): ")
    if proceed.lower() == 'yes':
        logging.info("User confirmed to proceed with file renaming.")
        process_files(ambiguous_files)
    else:
        logging.info("User chose not to proceed with the operation.")

    logging.info("Program completed.")

if __name__ == "__main__":
    main()
