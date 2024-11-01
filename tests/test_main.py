import pytest
import os
import logging
import tempfile
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from datetime import datetime
import json
import sys
from pathlib import Path
import pyodbc
from azure.identity import DefaultAzureCredential

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.main import (
    main,
    process_failed_record,
    setup_logging,
    load_config,
    acquire_lock,
    release_lock,
    LockError,
    generate_new_filename
)

@pytest.fixture
def mock_config():
    return {
        "azure_sql_server": "test-server",
        "azure_sql_database": "test-db",
        "log_directory": "test_logs",
        "batch_size": 50,
        "retry_limit": 3,
        "processing_timeout": 300
    }

@pytest.fixture
def mock_record():
    record = Mock()
    record.contract_payments_id = 1
    record.deal_name = "test_deal"
    record.file_name = "test_file.pdf"
    record.full_file_path = "/path/to/test_file.pdf"
    record.deal_id = 100
    record.status = "Failed"
    record.failure_reason = "File pattern does not match required format"
    return record

@pytest.fixture
def mock_db_connection():
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    return conn

class TestConfigurationLoading:
    def test_load_config_success(self, tmp_path):
        """Test successful configuration loading"""
        config_data = {
            "azure_sql_server": "test-server",
            "azure_sql_database": "test-db",
            "log_directory": "test_logs",
            "batch_size": 50
        }
        config_file = tmp_path / "data" / "config.json"
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
            config = load_config()
            assert config == config_data
            assert all(key in config for key in ["azure_sql_server", "azure_sql_database", "log_directory"])

    def test_load_config_missing_file(self):
        """Test handling of missing configuration file"""
        with patch('builtins.open', side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                load_config()

    def test_load_config_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in config file"""
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(json.JSONDecodeError):
                load_config()

class TestLoggingSetup:
    def test_setup_logging_directory_creation(self, tmp_path):
        """Test logging directory creation and file handling"""
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir))
        
        assert os.path.exists(log_dir)
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"doc_classification_{current_date}.log"
        
        logging.info("Test log message")
        assert os.path.exists(log_file)
        
        with open(log_file) as f:
            log_content = f.read()
            assert "Test log message" in log_content

    def test_setup_logging_file_permissions(self, tmp_path):
        """Test logging file permissions"""
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir))
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"doc_classification_{current_date}.log"
        
        assert os.access(log_file.parent, os.W_OK)
        logging.info("Test message")
        assert os.access(log_file, os.R_OK)

    @patch('src.main.datetime')
    def test_setup_logging_rotation(self, mock_datetime, tmp_path):
        """Test log rotation functionality"""
        # Mock datetime.now() to return a fixed date
        fixed_date = datetime(2024, 1, 1, 12, 0)
        mock_datetime.now.return_value = fixed_date
        mock_datetime.strftime = datetime.strftime  # Keep the real strftime
        
        log_dir = tmp_path / "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Create test log files before setting up logging
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        test_files = []
        for date in dates:
            log_file = log_dir / f"doc_classification_{date}.log"
            with open(log_file, 'w') as f:
                f.write(f"Log for {date}")
            test_files.append(log_file)

        # Now verify the files exist
        actual_files = sorted([f.name for f in log_dir.glob("*.log")])
        expected_files = sorted([f"doc_classification_{date}.log" for date in dates])
        assert actual_files == expected_files

class TestRecordProcessing:
    def test_process_failed_record_file_not_found(self, mock_db_connection, mock_record):
        """Test handling of missing files"""
        with patch('os.path.exists', return_value=False), \
             patch('src.main.find_file_path', return_value=None):
            
            process_failed_record(mock_db_connection, mock_record)
            
            # Verify error handling in the execute call args
            args = mock_db_connection.cursor().execute.call_args_list
            has_error_msg = any("File not found" in str(call_args) for call_args in args)
            assert has_error_msg

    def test_process_failed_record_rename_error(self, mock_db_connection, mock_record):
        """Test handling of file rename errors"""
        with patch('os.path.exists', return_value=True), \
             patch('src.main.validate_new_filename', return_value=(True, "")), \
             patch('src.main.check_duplicate_filename', return_value=False), \
             patch('src.main.rename_file', return_value=(False, "Access denied")):
            
            process_failed_record(mock_db_connection, mock_record)
            
            # Verify error handling in the execute call args
            args = mock_db_connection.cursor().execute.call_args_list
            has_error_msg = any("Access denied" in str(call_args) for call_args in args)
            assert has_error_msg

    def test_process_failed_record_duplicate_filename(self, mock_db_connection, mock_record):
        """Test handling of duplicate filenames"""
        with patch('os.path.exists', return_value=True), \
             patch('src.main.validate_new_filename', return_value=(True, "")), \
             patch('src.main.check_duplicate_filename', return_value=True):
            
            process_failed_record(mock_db_connection, mock_record)
            
            # Verify error handling in all execute calls
            args = mock_db_connection.cursor().execute.call_args_list
            has_error_msg = any("Duplicate filename" in str(call_args) for call_args in args)
            assert has_error_msg

class TestMainFunction:
    @patch('src.main.connect_to_azure_db')
    @patch('src.main.get_failed_unprocessed_records')
    def test_main_no_records(self, mock_get_records, mock_connect_db, 
                            mock_config, tmp_path):
        """Test main execution with no records to process"""
        lock_file = tmp_path / "test.lock"
        
        # Create mock connection with explicit close method
        mock_conn = Mock()
        mock_conn.close = Mock()
        
        # Set up the mock connection
        mock_connect_db.return_value = mock_conn
        mock_get_records.return_value = []
        
        # Mock the load_config to return our test config
        with patch('src.main.load_config', return_value=mock_config):
            # Execute main function
            main(str(lock_file))
            
            # Verify connection was closed
            mock_conn.close.assert_called_once()
            
            # Verify proper logging
            mock_get_records.assert_called_once_with(mock_conn)
            assert not os.path.exists(lock_file), "Lock file should be released"

    @patch('src.main.connect_to_azure_db')
    @patch('src.main.get_failed_unprocessed_records')
    @patch('src.main.process_failed_record')
    def test_main_partial_failure(self, mock_process_record, mock_get_records, 
                                mock_connect_db, mock_config, tmp_path):
        """Test main execution with some record processing failures"""
        lock_file = tmp_path / "test.lock"
        mock_conn = Mock()
        mock_records = [Mock(), Mock(), Mock()]
        
        mock_connect_db.return_value = mock_conn
        mock_get_records.return_value = mock_records
        
        # Update side effect to not raise exception
        mock_process_record.side_effect = [None, None, None]
        
        with patch('src.main.load_config', return_value=mock_config):
            main(str(lock_file))
        
        assert mock_process_record.call_count == len(mock_records)
        mock_conn.close.assert_called_once()

class TestErrorHandling:
    def test_process_failed_record_database_error(self, mock_db_connection, mock_record):
        """Test handling of database errors during record processing"""
        # Configure the mock cursor
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = pyodbc.Error('Database error')
        mock_db_connection.cursor.return_value = mock_cursor
        
        with patch('os.path.exists', return_value=True):
            try:
                process_failed_record(mock_db_connection, mock_record)
            except pyodbc.Error:
                pass  # Expected exception
            
            # Verify rollback was called
            mock_db_connection.rollback.assert_called_once()

    def test_process_failed_record_filesystem_error(self, mock_db_connection, mock_record):
        """Test handling of filesystem errors during record processing"""
        mock_cursor = Mock()
        mock_db_connection.cursor.return_value = mock_cursor
        
        # Set up the execute mock to capture the failure reason
        def mock_execute(*args, **kwargs):
            if len(args) > 0 and "UPDATE contract_payments SET" in args[0]:
                # args[0] is SQL query, args[1:] are parameters
                assert "Permission denied" in args[1][2]  # Check failure reason parameter
        mock_cursor.execute.side_effect = mock_execute
        
        with patch('os.path.exists', return_value=True), \
             patch('src.main.rename_file', side_effect=OSError("Permission denied")), \
             patch('src.main.validate_new_filename', return_value=(True, "")), \
             patch('src.main.check_duplicate_filename', return_value=False):

            process_failed_record(mock_db_connection, mock_record)
            
            # Verify execute was called
            mock_cursor.execute.assert_called()
            
            # Get the failure reason from the last execute call
            last_call = mock_cursor.execute.call_args_list[-1]
            assert "Permission denied" in last_call[0][1][2]

    def test_process_failed_record_unexpected_error(self, mock_db_connection, mock_record):
        """Test handling of unexpected errors during record processing"""
        mock_cursor = Mock()
        mock_db_connection.cursor.return_value = mock_cursor
        
        # Set up the execute mock to capture the failure reason
        def mock_execute(*args, **kwargs):
            if len(args) > 0 and "UPDATE contract_payments SET" in args[0]:
                assert "Unexpected error" in args[1][2]  # Check failure reason parameter
        mock_cursor.execute.side_effect = mock_execute

        with patch('os.path.exists', side_effect=Exception("Unexpected error")):
            process_failed_record(mock_db_connection, mock_record)
            
            # Verify execute was called
            mock_cursor.execute.assert_called()
            
            # Get the failure reason from the last execute call
            last_call = mock_cursor.execute.call_args_list[-1]
            assert "Unexpected error" in last_call[0][1][2]

if __name__ == '__main__':
    pytest.main([__file__])