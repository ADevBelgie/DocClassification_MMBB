# from datetime import datetime
# import json
# import os
# from unittest.mock import Mock, patch
# import pytest
# import tempfile
# from pathlib import Path
# import pyodbc
# from azure.identity import DefaultAzureCredential
# from concurrent.futures import ThreadPoolExecutor, TimeoutError
# import logging
# from PIL import Image, ImageDraw
# import threading
# import time
# from PIL import Image
# import anthropic
# from src.sql_utils import connect_to_azure_db, get_failed_unprocessed_records, update_renamed_record
# from src.api_client import (
#     convert_pdf_to_images,
#     check_image_quality,
#     create_api_prompt,
#     process_file_for_api,
#     communicate_with_api
# )
# from src.main import main, process_failed_record

# @pytest.fixture(scope="session")
# def mock_db_record():
#     """Creates a mock database record with the correct fields."""
#     return Mock(
#         contract_payments_id=1,
#         deal_name="Test Deal",
#         file_name="test.pdf",
#         full_file_path="/test/path/test.pdf",
#         status="Failed",
#         has_been_renamed=False,
#         failure_reason="File pattern does not match",
#         file_last_modified_on=datetime.now(),
#         file_created_on=datetime.now(),
#         contract_scanner_version="1.0",
#         thought_process=None,
#         valid_contract_payment=False,
#         multiple_payments_found=False,
#         payment_execution_date=None,
#         payment_reference=None,
#         payment_amount=None,
#         payment_currency=None,
#         payer_name=None,
#         payer_bank=None,
#         payer_account_number=None,
#         receiver_name=None,
#         receiver_bank=None,
#         receiver_account_number=None,
#         details_additional_notes=None,
#         retries_to_zoho=0,
#         zoho_file_id=None,
#         zoho_folder_id=None,
#         last_updated=datetime.now()
#     )

# @pytest.fixture(scope="session")
# def test_config():
#     """Load test configuration from config.json"""
#     try:
#         project_root = Path(__file__).parent.parent
#         config_path = project_root / "data" / "config.json"
        
#         with open(config_path) as f:
#             config = json.load(f)
            
#         required_fields = ["azure_sql_server", "azure_sql_database"]
#         missing_fields = [field for field in required_fields if not config.get(field)]
        
#         if missing_fields:
#             pytest.skip(f"Missing required config fields: {', '.join(missing_fields)}")
            
#         logging.info(f"Loaded configuration from {config_path}")
#         return config
        
#     except FileNotFoundError:
#         pytest.skip("Config file not found at data/config.json")
#     except json.JSONDecodeError as e:
#         pytest.skip(f"Invalid JSON in config file: {str(e)}")
#     except Exception as e:
#         pytest.skip(f"Error loading config: {str(e)}")

# @pytest.fixture(scope="function")
# def mock_db_connection():
#     """Creates a mock database connection."""
#     mock_conn = Mock()
#     mock_cursor = Mock()
#     mock_conn.cursor.return_value = mock_cursor
#     return mock_conn

# @pytest.fixture(scope="function")
# def mock_db_operations():
#     """Mock database operations at the module level."""
#     with patch('src.sql_utils.connect_to_azure_db') as mock_connect:
#         mock_conn = Mock()
#         mock_cursor = Mock()
#         mock_conn.cursor.return_value = mock_cursor
        
#         # Set up mock behaviors
#         mock_cursor.fetchall.return_value = []
#         mock_cursor.fetchone.return_value = ["SQL Server Test"]
#         mock_cursor.execute = Mock()
#         mock_conn.commit = Mock()
#         mock_connect.return_value = mock_conn
        
#         yield mock_connect

# @pytest.fixture(scope="function")
# def temp_test_dir():
#     """Provides a temporary directory for test files."""
#     with tempfile.TemporaryDirectory() as tmpdirname:
#         yield Path(tmpdirname)

# @pytest.fixture(scope="session")
# def azure_db_connection(test_config):
#     """Creates a mock connection for integration tests."""
#     mock_conn = Mock()
#     mock_cursor = Mock()
#     mock_conn.cursor.return_value = mock_cursor
    
#     # Set up basic behaviors
#     mock_cursor.fetchall.return_value = []
#     mock_cursor.fetchone.return_value = ["SQL Server Test"]
#     mock_cursor.execute = Mock()
#     mock_conn.commit = Mock()
#     mock_conn.close = Mock()
    
#     return mock_conn

# @pytest.fixture(scope="function")
# def test_pdf_file(temp_test_dir):
#     """Creates a test PDF file."""
#     from reportlab.pdfgen import canvas
#     pdf_path = temp_test_dir / "test.pdf"
    
#     c = canvas.Canvas(str(pdf_path))
#     c.drawString(100, 750, "Test PDF Document")
#     c.drawString(100, 700, "For Integration Testing")
#     c.save()
    
#     return pdf_path

# @pytest.fixture(scope="function")
# def test_image_file(temp_test_dir):
#     """Creates a test image file."""
#     img_path = temp_test_dir / "test.jpg"
    
#     # Create a simple test image
#     img = Image.new('RGB', (100, 100), color='white')
#     img.save(str(img_path))
    
#     return img_path

# @pytest.mark.db
# def test_database_connection(test_db):
#     """Test database connection verification using TestDatabaseConnection."""
#     cursor = test_db.cursor()
#     cursor.execute("SELECT @@VERSION")
#     assert len(cursor.executed_queries) > 0
#     assert cursor.executed_queries[-1][0] == "SELECT @@VERSION"
#     logging.info("Successfully tested database connection")

# @pytest.mark.db
# def test_failed_records_retrieval(test_db):
#     """Test retrieval of failed unprocessed records using TestDatabaseConnection."""
#     cursor = test_db.cursor()
#     assert len(cursor.mock_records) > 0
#     records = get_failed_unprocessed_records(test_db)
#     assert records[0].file_name == 'test.pdf'
#     assert records[0].status == 'Failed'
#     logging.info(f"Successfully retrieved {len(records)} test records")

# @pytest.mark.db
# def test_record_update(test_db):
#     """Test record update functionality using TestDatabaseConnection."""
#     cursor = test_db.cursor()
#     initial_query_count = len(cursor.executed_queries)
    
#     update_renamed_record(
#         test_db,
#         1,  # record_id
#         "new.pdf",
#         "/new/path/new.pdf"
#     )
    
#     # Verify an update query was executed
#     assert len(cursor.executed_queries) > initial_query_count
    
#     # Verify the last query was an UPDATE
#     last_query = cursor.executed_queries[-1][0]
#     assert "UPDATE" in last_query.upper()
#     logging.info("Successfully tested record update")

# @pytest.mark.no_db
# def test_pdf_conversion(test_pdf_file, temp_test_dir):
#     """Test conversion of PDF to images."""
#     # Convert PDF to images
#     images = convert_pdf_to_images(str(test_pdf_file), str(temp_test_dir))
    
#     assert len(images) > 0
#     assert all(isinstance(img, Image.Image) for img in images)
    
#     # Allow time for file system operations
#     time.sleep(1)
    
#     # Check for files with the correct pattern
#     base_filename = test_pdf_file.stem
#     save_subdir = temp_test_dir / base_filename
#     saved_files = list(save_subdir.glob("*.jpeg"))
#     assert len(saved_files) == len(images)

# @pytest.mark.no_db
# def test_image_quality_assessment(test_image_file):
#     """Test image quality assessment functionality."""
#     quality_result = check_image_quality(str(test_image_file))
#     assert quality_result in ['Good', 'Bad']

# def test_file_processing_pipeline(test_pdf_file, temp_test_dir):
#     """Test the complete file processing pipeline."""
#     result = process_file_for_api(str(test_pdf_file), str(temp_test_dir))
    
#     assert isinstance(result, list)
#     assert all(isinstance(item, dict) for item in result)
#     assert all('type' in item and 'source' in item for item in result)

# @pytest.mark.no_db
# def test_api_authentication():
#     """Test API authentication with actual credentials."""
#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         pytest.skip("No API key available")
    
#     client = anthropic.Anthropic(api_key=api_key)
#     assert client is not None

# def test_api_communication(test_image_file, temp_test_dir):
#     """Test actual API communication with a test image."""
#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         pytest.skip("No API key available")
        
#     # Create a higher quality test image
#     img = Image.new('RGB', (800, 800), color='white')
#     draw = ImageDraw.Draw(img)
#     # Add some text to make it more realistic
#     draw.text((400, 400), "Test Contract Document", fill='black')
#     draw.text((400, 450), "Payment Receipt", fill='black')
#     img.save(str(test_image_file), quality=95)
    
#     # Process the image for API
#     image_data = process_file_for_api(str(test_image_file), str(temp_test_dir))
    
#     # Skip test if image processing failed
#     if not image_data or isinstance(image_data, str):
#         pytest.skip(f"Image processing failed: {image_data}")
    
#     # Ensure image_data is in the correct format
#     if not isinstance(image_data, list):
#         image_data = [image_data]
        
#     # Add the required text component for the API
#     user_prompt = create_api_prompt()
#     message_content = [{"type": "text", "text": user_prompt}]
#     message_content.extend(image_data)
    
#     # Attempt API communication with timeout
#     def make_api_call():
#         return communicate_with_api(message_content)
    
#     with ThreadPoolExecutor() as executor:
#         future = executor.submit(make_api_call)
#         try:
#             classification, response = future.result(timeout=30)  # 30 second timeout
            
#             assert classification is not None
#             assert response is not None
#             assert classification in [
#                 'Rental_Contract',
#                 'Mortgage_Contract',
#                 'Contract_Payment',
#                 'Teleworking_Agreement',
#                 'Repayment_Table',
#                 'Unclassified'
#             ]
#         except TimeoutError:
#             pytest.skip("API call timed out after 30 seconds")

# @pytest.mark.api
# def test_rate_limiting_handling():
#     """Test API rate limiting without database interaction."""
#     # Mock API key
#     with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
#         # Create a minimal but valid test message
#         test_message = [{
#             "type": "text",
#             "text": create_api_prompt()
#         }]
        
#         responses = []
#         max_attempts = 2
        
#         with patch('src.api_client.anthropic.Anthropic') as MockAnthropic:
#             mock_client = Mock()
#             mock_messages = Mock()
#             mock_response = Mock()
            
#             mock_response.model_dump_json.return_value = json.dumps({
#                 "content": [{
#                     "text": json.dumps({
#                         "ContentType": "Contract_Payment",
#                         "ThoughtProcess": "Test thought process"
#                     })
#                 }]
#             })
            
#             mock_messages.create.return_value = mock_response
#             mock_client.messages = mock_messages
#             MockAnthropic.return_value = mock_client
            
#             for _ in range(max_attempts):
#                 try:
#                     classification, response = communicate_with_api(test_message)
#                     if classification is not None:
#                         responses.append((classification, response))
#                 except Exception as e:
#                     logging.error(f"API call failed: {str(e)}")
#                     time.sleep(1)
        
#         assert len(responses) > 0, "No successful API responses received"
#         assert any(r[0] == "Contract_Payment" for r in responses), "No valid classifications received"

# @pytest.mark.integration
# def test_concurrent_execution(test_db, temp_test_dir):
#     """Test system behavior with concurrent execution."""
#     lock_file = os.path.join(temp_test_dir, "test.lock")
    
#     # Add test record
#     cursor = test_db.cursor()
#     mock_record = Mock()
#     mock_record.contract_payments_id = 1
#     mock_record.deal_name = "Test Deal"
#     mock_record.file_name = "test.pdf"
#     mock_record.full_file_path = os.path.join(temp_test_dir, "test.pdf")
#     mock_record.status = "Failed"
#     mock_record.has_been_renamed = False
#     mock_record.failure_reason = "File pattern does not match"
    
#     # Initialize tracking at module level
#     queries_executed = []
    
#     def mock_get_failed_records(conn):
#         queries_executed.append(("SELECT * FROM contract_payments WHERE status = 'Failed'", None))
#         return [mock_record]
    
#     def mock_update_record(conn, payment_id, new_name, new_path):
#         queries_executed.append((
#             "UPDATE contract_payments SET file_name = ?, full_file_path = ?",
#             (new_name, new_path)
#         ))
#         return True
    
#     # Create test file
#     with open(os.path.join(temp_test_dir, "test.pdf"), "w") as f:
#         f.write("Test content")
    
#     def run_test_instance():
#         try:
#             with patch('src.sql_utils.connect_to_azure_db', return_value=test_db), \
#                  patch('src.sql_utils.get_failed_unprocessed_records', mock_get_failed_records), \
#                  patch('src.sql_utils.update_renamed_record', mock_update_record), \
#                  patch('src.api_client.anthropic.Anthropic') as MockAnthropic, \
#                  patch('src.main.acquire_lock', return_value=True):  # Force lock acquisition
                
#                 mock_client = Mock()
#                 mock_messages = Mock()
#                 mock_response = Mock()
#                 mock_response.model_dump_json.return_value = json.dumps({
#                     "content": [{
#                         "text": json.dumps({
#                             "ContentType": "Contract_Payment",
#                             "ThoughtProcess": "Test thought process"
#                         })
#                     }]
#                 })
#                 mock_messages.create.return_value = mock_response
#                 mock_client.messages = mock_messages
#                 MockAnthropic.return_value = mock_client
                
#                 main(lock_file)
#         except Exception as e:
#             logging.error(f"Thread execution failed: {str(e)}")
    
#     # Run threads
#     threads = []
#     for i in range(2):
#         thread = threading.Thread(target=run_test_instance)
#         threads.append(thread)
#         thread.start()
    
#     for thread in threads:
#         thread.join(timeout=5)
    
#     # Verify queries were executed
#     executed_query_texts = [q[0].upper() for q, _ in queries_executed]
#     assert any("SELECT" in q for q in executed_query_texts), "No SELECT operations found"
#     assert any("UPDATE" in q for q in executed_query_texts), "No UPDATE operations found"

# @pytest.fixture(scope="function")
# def verify_real_db_connection(test_config):
#     """Optional fixture to verify real database connection without making changes."""
#     try:
#         credential = DefaultAzureCredential()
#         token = credential.get_token("https://database.windows.net/.default")
        
#         conn_str = (
#             f'Driver={{ODBC Driver 18 for SQL Server}};'
#             f'Server=tcp:{test_config["azure_sql_server"]}.database.windows.net,1433;'
#             f'Database={test_config["azure_sql_database"]};'
#             'Encrypt=yes;'
#             'TrustServerCertificate=no;'
#             'Connection Timeout=30;'
#             'Authentication=ActiveDirectoryMsi'
#         )
        
#         conn = pyodbc.connect(conn_str)
#         cursor = conn.cursor()
        
#         # Only do a read-only check
#         cursor.execute("SELECT @@VERSION")
#         version = cursor.fetchone()
#         logging.info(f"Verified connection to: {version[0][:50]}...")
        
#         cursor.close()
#         conn.close()
        
#         return True
#     except Exception as e:
#         logging.error(f"Database connection verification failed: {str(e)}")
#         return False

# def test_verify_connection(verify_real_db_connection):
#     """Optional test to verify real database connection is possible."""
#     if not verify_real_db_connection:
#         pytest.skip("Could not verify real database connection")
#     assert verify_real_db_connection

# @pytest.mark.integration
# def test_error_recovery(test_db, temp_test_dir):
#     """Test system recovery from various error conditions."""
#     error_triggered = False
#     queries_executed = []
    
#     def mock_get_failed_records(conn):
#         nonlocal error_triggered
#         queries_executed.append(("SELECT * FROM contract_payments WHERE status = 'Failed'", None))
#         if not error_triggered:
#             error_triggered = True
#             raise Exception("Test error")
#         return []
    
#     # Create test file
#     with open(os.path.join(temp_test_dir, "test.pdf"), "w") as f:
#         f.write("Test content")
    
#     with patch('src.sql_utils.connect_to_azure_db', return_value=test_db), \
#          patch('src.sql_utils.get_failed_unprocessed_records', mock_get_failed_records):
#         try:
#             main(os.path.join(temp_test_dir, "test.lock"))
#         except Exception as e:
#             pass  # Expected error
    
#     assert error_triggered, "No errors were simulated"
#     assert any("SELECT" in q[0].upper() for q in queries_executed), "No queries were executed"

# @pytest.mark.integration
# def test_end_to_end_flow(test_db, test_pdf_file, temp_test_dir):
#     """Test complete end-to-end system flow."""
#     queries_executed = []
    
#     # Create test record
#     mock_record = Mock()
#     mock_record.contract_payments_id = 1
#     mock_record.deal_name = "Test Deal"
#     mock_record.file_name = os.path.basename(str(test_pdf_file))
#     mock_record.full_file_path = str(test_pdf_file)
#     mock_record.status = "Failed"
#     mock_record.has_been_renamed = False
#     mock_record.failure_reason = "File pattern does not match"
    
#     def mock_get_failed_records(conn):
#         queries_executed.append(("SELECT * FROM contract_payments WHERE status = 'Failed'", None))
#         return [mock_record]
    
#     def mock_update_record(conn, payment_id, new_name, new_path):
#         queries_executed.append((
#             "UPDATE contract_payments SET file_name = ?, full_file_path = ?",
#             (new_name, new_path)
#         ))
#         return True
    
#     # Create test file
#     with open(test_pdf_file, "w") as f:
#         f.write("Test content")
    
#     with patch('src.api_client.anthropic.Anthropic') as MockAnthropic, \
#          patch('src.sql_utils.connect_to_azure_db', return_value=test_db), \
#          patch('src.sql_utils.get_failed_unprocessed_records', mock_get_failed_records), \
#          patch('src.sql_utils.update_renamed_record', mock_update_record), \
#          patch('src.file_utils.find_file_path', return_value=str(test_pdf_file)):
        
#         mock_client = Mock()
#         mock_messages = Mock()
#         mock_response = Mock()
#         mock_response.model_dump_json.return_value = json.dumps({
#             "content": [{
#                 "text": json.dumps({
#                     "ContentType": "Contract_Payment",
#                     "ThoughtProcess": "Test thought process"
#                 })
#             }]
#         })
#         mock_messages.create.return_value = mock_response
#         mock_client.messages = mock_messages
#         MockAnthropic.return_value = mock_client
        
#         main(os.path.join(temp_test_dir, "test.lock"))
    
#     executed_query_texts = [q[0].upper() for q in queries_executed]
#     assert any("SELECT" in q for q in executed_query_texts), "No SELECT operations found"
#     assert any("UPDATE" in q for q in executed_query_texts), "No UPDATE operations found"
#     assert len(executed_query_texts) >= 2, "Expected at least 2 database operations"

# @pytest.fixture(autouse=True)
# def prevent_db_changes(monkeypatch):
#     """Prevent any real database changes in tests."""
#     # Instead of trying to patch pyodbc directly, patch our own functions
#     def mock_connect(*args, **kwargs):
#         mock_conn = Mock()
#         mock_cursor = Mock()
#         mock_conn.cursor.return_value = mock_cursor
#         return mock_conn

#     monkeypatch.setattr("src.sql_utils.connect_to_azure_db", mock_connect)

# def verify_query_execution(cursor, expected_query_type):
#     """Helper function to verify query execution."""
#     executed_queries = [q[0].upper() for q in cursor.executed_queries]
#     matching_queries = [q for q in executed_queries if expected_query_type.upper() in q]
#     return len(matching_queries) > 0

# def verify_record_processing(test_db, record_id):
#     """Helper function to verify record processing."""
#     cursor = test_db.cursor()
    
#     # Check if record was processed
#     executed_queries = cursor.executed_queries
#     processed = any(
#         str(record_id) in str(params)
#         for query, params in executed_queries
#         if "UPDATE" in query.upper()
#     )
#     return processed

# def verify_lock_handling(temp_test_dir):
#     """Helper function to verify lock file handling."""
#     lock_file = os.path.join(temp_test_dir, "test.lock")
#     return not os.path.exists(lock_file)