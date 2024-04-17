import os
import re

def find_ambiguous_filenames(base_path):
    """
    Scans through the directory tree starting at `base_path` for folders matching specific patterns and logs all file paths.
    Args:
    base_path (str): The root directory to start scanning from.
    """
    # Define the pattern for the folders of interest
    folder_pattern = re.compile(r".*-( Housing Cost| Home Mortgage| Home rent)$")
    ambiguous_files = []

    # Walk through the directory
    for root, dirs, files in os.walk(base_path):
        # Check if the current directory matches the pattern
        if folder_pattern.search(root):
            for file in files:
                # Construct full file path
                full_path = os.path.join(root, file)
                ambiguous_files.append(full_path)
    
    return ambiguous_files

def write_to_file(file_list, filename):
    """
    Writes each path in `file_list` to a file named `filename`.
    Args:
    file_list (list of str): List of file paths to write.
    filename (str): Path to the file where to write the paths.
    """
    with open(filename, 'w') as file:
        for file_path in file_list:
            file.write(file_path + '\n')

if __name__ == "__main__":
    # Example usage
    base_path = "path\\to\\your\\network\\drive\\Deals"  # Update this path to your specific base path
    ambiguous_files = find_ambiguous_filenames(base_path)
    write_to_file(ambiguous_files, "data/Ambiguous_file_names.txt")
