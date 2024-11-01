from src.sql_utils import get_failed_unprocessed_records, update_renamed_record

def test_get_failed_unprocessed_records(mock_db_connection):
    def test_retrieval():
        mock_db_connection.cursor().fetchall.return_value = [
            (1, "Failed", 0, "test.pdf", "path/to/file")
        ]
        records = get_failed_unprocessed_records(mock_db_connection)
        assert len(records) > 0

def test_update_renamed_record(mock_db_connection):
    def test_successful_update():
        update_renamed_record(mock_db_connection, 1, "new.pdf", "/new/path")
        mock_db_connection.commit.assert_called_once()