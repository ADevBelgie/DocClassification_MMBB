import pytest
import os
import tempfile
import json
from unittest.mock import Mock

@pytest.fixture
def mock_config():
    return {
        "azure_sql_server": "test-server",
        "azure_sql_database": "test-db",
        "log_directory": "test_logs"
    }

@pytest.fixture
def temp_test_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

@pytest.fixture
def mock_db_connection():
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    return conn

class TestDatabaseConnection:
    """Test database connection class that mimics pyodbc connection behavior."""
    def __init__(self, test_mode=True):
        self.test_mode = test_mode
        self._cursor = None
        self.mock_records = []
        
    def cursor(self):
        if not self._cursor:
            self._cursor = TestDatabaseCursor(self)
        return self._cursor
        
    def commit(self):
        # Safe to call in test mode
        pass
        
    def rollback(self):
        # Safe to call in test mode
        pass
        
    def close(self):
        if self._cursor:
            self._cursor.close()
        self._cursor = None

class TestDatabaseCursor:
    """Test database cursor class that mimics pyodbc cursor behavior."""
    def __init__(self, connection):
        self.connection = connection
        self.mock_records = []
        self.executed_queries = []
        
    def execute(self, query, params=()):
        self.executed_queries.append((query, params))
        return self
        
    def fetchall(self):
        return self.mock_records
        
    def fetchone(self):
        return self.mock_records[0] if self.mock_records else None
        
    def close(self):
        pass
        
    def __iter__(self):
        return iter(self.mock_records)

def pytest_configure(config):
    """Add test markers for different test categories."""
    config.addinivalue_line("markers", "db: mark test as using database")
    config.addinivalue_line("markers", "api: mark test as using API")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "no_db: mark test as not using database")

@pytest.fixture(scope="function")
def test_db():
    """Create a test database connection with mocked data."""
    connection = TestDatabaseConnection(test_mode=True)
    cursor = connection.cursor()
    
    # Setup some default mock records
    mock_record = Mock()
    mock_record.contract_payments_id = 1
    mock_record.deal_name = "Test Deal"
    mock_record.file_name = "test.pdf"
    mock_record.full_file_path = "/test/path/test.pdf"
    mock_record.status = "Failed"
    mock_record.has_been_renamed = False
    mock_record.failure_reason = "File pattern does not match"
    
    cursor.mock_records = [mock_record]
    
    return connection