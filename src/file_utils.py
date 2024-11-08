"""
file_utils.py

This module provides utility functions focused on file renaming operations and path validation.
It supports file management tasks within the application by offering functionality to rename files
and verify their locations.
"""
import os
import logging
import subprocess
import time

def find_file_path(deal_name: str, file_name: str, max_retries: int = 3, initial_delay: int = 10) -> str | None:
    """
    Finds the current file path using PowerShell script.

    Args:
        deal_name: Name of the deal folder
        file_name: Name of the file to find
        max_retries: Number of retries if file not found
        initial_delay: Initial delay in seconds between retries

    Returns:
        str: Full file path if found, None if not found
    """
    script_path = os.path.join('tools', 'findFilepath.ps1')
    
    # Handle special characters in parameters
    escaped_file_name = f'"{file_name.replace('"', '`"')}"'
    escaped_deal_name = f'"{deal_name.replace('"', '`"')}"'
    
    ps_command = [
        'powershell.exe',
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        f'& "{script_path}" -FileName {escaped_file_name} -FolderName {escaped_deal_name}'
    ]

    logging.info(f"Searching for file: {file_name} in folder: {deal_name}")

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logging.info(f"Retry attempt {attempt + 1}/{max_retries}")
                
            result = subprocess.run(
                ps_command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # Log PowerShell errors if any
            if result.stderr:
                logging.error(f"PowerShell error: {result.stderr}")

            # Check for PowerShell execution success
            if result.returncode != 0:
                logging.error(f"PowerShell execution failed with return code: {result.returncode}")
                if attempt < max_retries - 1:
                    time.sleep(initial_delay * (attempt + 1))
                    continue
                return None

            # Process the output
            if result.stdout:
                for line in result.stdout.splitlines():
                    if line.startswith("RESULT:"):
                        path = line.split("RESULT:", 1)[1].strip()
                        if path == "NOT_FOUND":
                            logging.info("File not found in specified locations")
                            break
                        if os.path.exists(path):
                            logging.info(f"Found file: {path}")
                            return path
                        else:
                            logging.error(f"Found path doesn't exist: {path}")

            if attempt < max_retries - 1:
                delay = initial_delay * (attempt + 1)
                logging.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)

        except Exception as e:
            logging.error(f"Error during file search: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(initial_delay * (attempt + 1))
                continue
            return None

    logging.error(f"Failed to find file after {max_retries} attempts")
    return None

def rename_file(original_path, new_name):
    """
    Renames a file while maintaining its directory location and handles duplicates.

    Args:
        original_path (str): The full path of the original file.
        new_name (str): Classification string that will become the new filename.

    Returns:
        tuple: (bool, str) - (Success status, new path if successful or error message if failed)
    """
    try:
        directory, _ = os.path.split(original_path)
        _, extension = os.path.splitext(original_path)
        new_base_name = new_name  # Use classification directly as the new name
        new_path = os.path.join(directory, f"{new_base_name}{extension}")
        counter = 1

        # Handle duplicate filenames by appending a counter
        while os.path.exists(new_path):
            new_path = os.path.join(directory, f"{new_base_name} ({counter}){extension}")
            counter += 1

        os.rename(original_path, new_path)
        logging.info(f"File renamed: {new_path}")
        return True, new_path

    except OSError as e:
        error_msg = f"Error renaming file {original_path}: {str(e)}"
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error renaming {original_path}: {str(e)}"
        logging.error(error_msg)
        return False, error_msg

def validate_new_filename(filename):
    """
    Validates that a proposed filename meets required criteria.
    
    Args:
        filename (str): Proposed new filename
        
    Returns:
        tuple: (bool, str) - (Is valid, Error message if invalid)
    """
    try:
        # Check for empty or None
        if not filename or not filename.strip():
            return False, "Filename cannot be empty"
            
        # Check length
        if len(filename) > 255:
            return False, "Filename is too long"
            
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            return False, f"Filename contains invalid characters: {invalid_chars}"
            
        # Must have an extension
        if '.' not in filename:
            return False, "Filename must have an extension"
            
        return True, ""
        
    except Exception as e:
        return False, f"Error validating filename: {str(e)}"