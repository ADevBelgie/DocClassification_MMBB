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