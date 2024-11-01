import os
import pytest
import shutil
from unittest.mock import patch, Mock
import subprocess
from pathlib import Path
import tempfile
from datetime import datetime

from src.file_utils import find_file_path, rename_file, validate_new_filename

@pytest.fixture
def test_directory():
    """Create a temporary directory for file operations testing."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

@pytest.fixture
def sample_files(test_directory):
    """Create sample files for testing."""
    # Create a nested directory structure
    deal_dir = os.path.join(test_directory, "test_deal")
    os.makedirs(deal_dir)
    
    # Create test files
    files = {
        "normal.pdf": "Test content",
        "special chars!@#.pdf": "Special characters content",
        "long_name" + "x" * 200 + ".pdf": "Long filename content",
        "existing.pdf": "Existing file content"
    }
    
    created_files = {}
    for filename, content in files.items():
        file_path = os.path.join(deal_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        created_files[filename] = file_path
    
    return created_files

class TestFindFilePath:
    """Tests for find_file_path function."""

    def test_find_existing_file(self, test_directory):
        """Test finding an existing file in the deals directory."""
        expected_path = os.path.join(test_directory, 'test_deal', 'test.pdf')
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            # Simulate exact PowerShell script output
            mock_result.stdout = (
                f"Searching for file: test.pdf\n"
                f"In folder: test_deal\n"
                f"Locations to search: Z:\\Zoho CRM\\Deals, Z:\\Zoho CRM\\Accounts\n"
                f"File found: {expected_path}\n"
                f"RESULT:{expected_path}\n"
                f"Search completed in 0.1234 seconds.\n"  # Added newline
            )
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            # Mock os.path.exists to return True for the expected path
            with patch('os.path.exists', return_value=True):  # Added this patch
                result = find_file_path("test_deal", "test.pdf")
                assert result is not None
                assert result == expected_path

    def test_file_not_found(self):
        """Test behavior when file is not found."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = (
                "Searching for file: nonexistent.pdf\n"
                "In folder: nonexistent_deal\n"
                "Locations to search: Z:\\Zoho CRM\\Deals, Z:\\Zoho CRM\\Accounts\n"
                "File not found in any of the specified locations.\n"
                "RESULT:NOT_FOUND\n"
                "Search completed in 0.1234 seconds."
            )
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = find_file_path("nonexistent_deal", "nonexistent.pdf")
            assert result is None

    def test_powershell_error(self):
        """Test handling of PowerShell script errors."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', "Error")
            result = find_file_path("test_deal", "test.pdf")
            assert result is None

    @pytest.mark.parametrize("deal_name,file_name,expected_path", [
        (
            "deal with spaces",
            "file with spaces.pdf",
            "Z:\\Zoho CRM\\Deals\\deal with spaces\\file with spaces.pdf"
        ),
        (
            "deal_normal",
            "file!@#$.pdf",
            "Z:\\Zoho CRM\\Deals\\deal_normal\\file!@#$.pdf"
        ),
        (
            "déàl",
            "fïlé.pdf",
            "Z:\\Zoho CRM\\Deals\\déàl\\fïlé.pdf"
        ),
    ])
    def test_special_characters(self, deal_name, file_name, expected_path):
        """Test handling of special characters in file and deal names."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            # Match PowerShell script output format exactly
            mock_result.stdout = (
                f"Searching for file: {file_name}\n"
                f"In folder: {deal_name}\n"
                f"Locations to search: Z:\\Zoho CRM\\Deals, Z:\\Zoho CRM\\Accounts\n"
                f"File found: {expected_path}\n"
                f"RESULT:{expected_path}\n"
                f"Search completed in 0.1234 seconds.\n"  # Added newline
            )
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Mock os.path.exists to return True for the expected path
            with patch('os.path.exists', return_value=True):  # Added this patch
                result = find_file_path(deal_name, file_name)
                assert result is not None
                assert result == expected_path

    def test_retry_on_timeout(self):
        """Test retry mechanism on temporary failures."""
        expected_path = "Z:\\Zoho CRM\\Deals\\test_deal\\test.pdf"
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = (
                f"Searching for file: test.pdf\n"
                f"In folder: test_deal\n"
                f"Locations to search: Z:\\Zoho CRM\\Deals, Z:\\Zoho CRM\\Accounts\n"
                f"File found: {expected_path}\n"
                f"RESULT:{expected_path}\n"
                f"Search completed in 0.1234 seconds.\n"
            )
            mock_result.returncode = 0
            
            # Simulate timeout then success
            mock_run.side_effect = [
                subprocess.TimeoutExpired(['powershell.exe'], 30),
                mock_result  # Return success on second attempt
            ]

            # Mock os.path.exists to return True for the expected path
            with patch('os.path.exists', return_value=True):
                result = find_file_path("test_deal", "test.pdf")
                assert result is not None
                assert result == expected_path
                assert mock_run.call_count == 2

class TestRenameFile:
    """Tests for rename_file function."""

    def test_successful_rename(self, test_directory):
        """Test successful file rename operation."""
        original_path = os.path.join(test_directory, "original.pdf")
        with open(original_path, "w") as f:
            f.write("test content")

        success, new_path = rename_file(original_path, "renamed.pdf")
        
        assert success
        assert os.path.exists(new_path)
        assert not os.path.exists(original_path)
        assert os.path.basename(new_path) == "renamed.pdf"

    def test_rename_nonexistent_file(self, test_directory):
        """Test attempting to rename a nonexistent file."""
        nonexistent_path = os.path.join(test_directory, "nonexistent.pdf")
        success, error_msg = rename_file(nonexistent_path, "new.pdf")
        
        assert not success
        assert "Error renaming file" in error_msg

    def test_rename_to_existing_file(self, test_directory):
        """Test rename when target filename already exists."""
        # Create original and existing target files
        original_path = os.path.join(test_directory, "original.pdf")
        existing_path = os.path.join(test_directory, "target.pdf")
        
        for path in [original_path, existing_path]:
            with open(path, "w") as f:
                f.write("test content")

        success, new_path = rename_file(original_path, "target.pdf")
        
        assert success
        assert os.path.exists(new_path)
        assert "target (1).pdf" in new_path

    def test_rename_with_special_characters(self, test_directory):
        """Test renaming with special characters in filename."""
        original_path = os.path.join(test_directory, "original.pdf")
        with open(original_path, "w") as f:
            f.write("test content")

        special_name = "special!@#$%^&().pdf"
        success, new_path = rename_file(original_path, special_name)
        
        assert success
        assert os.path.exists(new_path)
        assert os.path.basename(new_path) == special_name

    def test_rename_permission_error(self, test_directory):
        """Test rename operation when permission is denied."""
        original_path = os.path.join(test_directory, "original.pdf")
        with open(original_path, "w") as f:
            f.write("test content")

        # Mock os.rename to raise PermissionError
        with patch('os.rename') as mock_rename:
            mock_rename.side_effect = PermissionError("Permission denied")
            success, error_msg = rename_file(original_path, "new.pdf")
            
            assert not success
            assert "Permission denied" in error_msg
    
    def test_command_construction(self):
        """Test that the PowerShell command is constructed correctly."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = "RESULT:NOT_FOUND"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            find_file_path("test_deal", "test.pdf")

            # Verify the command construction
            mock_run.assert_called_with(
                [
                    'powershell.exe',
                    '-ExecutionPolicy', 'Bypass',
                    '-File', 'tools\\findFilepath.ps1',
                    '-FileName', 'test.pdf',
                    '-FolderName', 'test_deal'
                ],
                capture_output=True,
                text=True,
                check=True
            )

class TestValidateNewFilename:
    """Tests for validate_new_filename function."""

    @pytest.mark.parametrize("filename", [
        "normal.pdf",
        "file with spaces.pdf",
        "file-with-hyphens.pdf",
        "file_with_underscores.pdf",
        "file.with.dots.pdf",
        "file123.pdf",
    ])
    def test_valid_filenames(self, filename):
        """Test various valid filename patterns."""
        is_valid, error_msg = validate_new_filename(filename)
        assert is_valid
        assert error_msg == ""

    @pytest.mark.parametrize("filename,expected_error", [
        ("", "Filename cannot be empty"),
        ("no_extension", "Filename must have an extension"),
        ("file<>:\"/\\|?*.pdf", "Filename contains invalid characters"),
        ("." + "x" * 255 + ".pdf", "Filename is too long"),
    ])
    def test_invalid_filenames(self, filename, expected_error):
        """Test various invalid filename patterns."""
        is_valid, error_msg = validate_new_filename(filename)
        assert not is_valid
        assert expected_error in error_msg

    def test_none_filename(self):
        """Test validation with None as filename."""
        is_valid, error_msg = validate_new_filename(None)
        assert not is_valid
        assert "Filename cannot be empty" in error_msg

    def test_whitespace_filename(self):
        """Test validation with whitespace-only filename."""
        is_valid, error_msg = validate_new_filename("   ")
        assert not is_valid
        assert "Filename cannot be empty" in error_msg

    @pytest.mark.parametrize("filename", [
        "résumé.pdf",
        "документ.pdf",
        "文件.pdf",
        "ファイル.pdf"
    ])
    def test_unicode_filenames(self, filename):
        """Test validation of filenames with Unicode characters."""
        is_valid, error_msg = validate_new_filename(filename)
        assert is_valid
        assert error_msg == ""

    def test_max_length_boundary(self):
        """Test filename validation at maximum length boundary."""
        # Test exactly at max length (255 characters)
        max_length = 255 - len(".pdf")  # Account for extension
        max_name = "x" * max_length + ".pdf"
        is_valid, error_msg = validate_new_filename(max_name)
        assert is_valid
        assert error_msg == ""

        # Test one character over max length
        too_long = "x" * (max_length + 1) + ".pdf"
        is_valid, error_msg = validate_new_filename(too_long)
        assert not is_valid
        assert "Filename is too long" in error_msg