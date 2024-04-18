"""
file_utils.py consists of utility functions for file operations including searching, reading, and writing files. 
It supports the application by managing ambiguous filenames and logging them for reclassification, 
and scanning directories to identify files and folders of interest for processing.
"""
import os
import re

def write_to_file(file_list, filename):
    """
    Scans through the directory tree starting at `base_path` for folders matching specific patterns and logs all file paths.
    
    Parameters:
    base_path (str): The root directory to start scanning from.
    
    The function uses a regular expression to match directory names that indicate potential ambiguity in their contents.
    This is useful for identifying files that may require further inspection or reclassification.
    
    Example folder patterns matched: '*- Housing Cost', '*- Home Mortgage', '*- Home rent'
    """
    with open(filename, 'w') as file:
        for file_path in file_list:
            file.write(file_path + '\n')

def find_deal_folders(base_path):
    """
    Scans the directory tree from 'base_path' for folders matching specific patterns, logging the paths of both the folders and their contents.

    Args:
        base_path (str): The root directory from which the scan starts.

    Returns:
        dict: A dictionary mapping directory paths to lists of file paths within those directories.
    """
    deal_pattern = re.compile(r".*-( Housing Cost| Home rent| Home Mortgage Interest)$")
    deals_info = {}

    for root, dirs, files in os.walk(base_path):
        for dir in dirs:
            if deal_pattern.match(dir):
                full_dir_path = os.path.join(root, dir)
                file_paths = [os.path.join(full_dir_path, file) for file in os.listdir(full_dir_path) if os.path.isfile(os.path.join(full_dir_path, file))]
                deals_info[full_dir_path] = file_paths
    return deals_info