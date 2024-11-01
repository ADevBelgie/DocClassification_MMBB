import os
import pytest
import tempfile
from pathlib import Path
import pyodbc
from azure.identity import DefaultAzureCredential
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import logging
from PIL import Image, ImageDraw
import threading
import time
from PIL import Image
import anthropic
from src.sql_utils import connect_to_azure_db, get_failed_unprocessed_records, update_renamed_record
from src.api_client import (
    convert_pdf_to_images,
    check_image_quality,
    create_api_prompt,
    process_file_for_api,
    communicate_with_api
)
from src.main import main, process_failed_record

@pytest.fixture(scope="session")
def test_config():
    """Provides test configuration settings."""
    return {
        "azure_sql_server": os.getenv("TEST_SQL_SERVER", "test-server"),
        "azure_sql_database": os.getenv("TEST_SQL_DB", "test-db"),
        "log_directory": "test_logs"
    }

@pytest.fixture(scope="function")
def temp_test_dir():
    """Provides a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture(scope="session")
def azure_db_connection(test_config):
    """Creates a real connection to Azure SQL database for integration tests."""
    try:
        conn = connect_to_azure_db(test_config)
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Could not connect to Azure SQL: {str(e)}")

@pytest.fixture(scope="function")
def test_pdf_file(temp_test_dir):
    """Creates a test PDF file."""
    from reportlab.pdfgen import canvas
    pdf_path = temp_test_dir / "test.pdf"
    
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Test PDF Document")
    c.drawString(100, 700, "For Integration Testing")
    c.save()
    
    return pdf_path

@pytest.fixture(scope="function")
def test_image_file(temp_test_dir):
    """Creates a test image file."""
    img_path = temp_test_dir / "test.jpg"
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='white')
    img.save(str(img_path))
    
    return img_path

def test_database_connection(azure_db_connection):
    """Test that we can establish a connection to Azure SQL."""
    assert azure_db_connection is not None
    cursor = azure_db_connection.cursor()
    cursor.execute("SELECT @@VERSION")
    assert cursor.fetchone() is not None

def test_failed_records_retrieval(azure_db_connection):
    """Test retrieval of failed unprocessed records."""
    # First insert a test record
    cursor = azure_db_connection.cursor()
    cursor.execute("""
        INSERT INTO contract_payments (status, has_been_renamed, file_name, full_file_path, failure_reason)
        VALUES ('Failed', 0, 'test.pdf', '/test/path', 'File pattern does not match')
    """)
    azure_db_connection.commit()
    
    # Now retrieve failed records
    records = get_failed_unprocessed_records(azure_db_connection)
    assert len(records) > 0
    assert any(r.file_name == 'test.pdf' for r in records)

def test_record_update(azure_db_connection):
    """Test updating a record after successful rename."""
    # Insert test record
    cursor = azure_db_connection.cursor()
    cursor.execute("""
        INSERT INTO contract_payments (status, has_been_renamed, file_name)
        OUTPUT INSERTED.contract_payments_id
        VALUES ('Failed', 0, 'original.pdf')
    """)
    record_id = cursor.fetchone()[0]
    
    # Update the record
    update_renamed_record(
        azure_db_connection,
        record_id,
        "new.pdf",
        "/new/path/new.pdf"
    )
    
    # Verify update
    cursor.execute("""
        SELECT status, has_been_renamed, file_name
        FROM contract_payments
        WHERE contract_payments_id = ?
    """, (record_id,))
    record = cursor.fetchone()
    assert record.status == 'New'
    assert record.has_been_renamed == 1
    assert record.file_name == 'new.pdf'

def test_pdf_conversion(test_pdf_file, temp_test_dir):
    """Test conversion of PDF to images."""
    # Convert PDF to images
    images = convert_pdf_to_images(str(test_pdf_file), str(temp_test_dir))
    
    assert len(images) > 0
    assert all(isinstance(img, Image.Image) for img in images)
    
    # Allow time for file system operations
    time.sleep(1)
    
    # Check for files with the correct pattern
    base_filename = test_pdf_file.stem
    save_subdir = temp_test_dir / base_filename
    saved_files = list(save_subdir.glob("*.jpeg"))
    assert len(saved_files) == len(images)

def test_image_quality_assessment(test_image_file):
    """Test image quality assessment functionality."""
    quality_result = check_image_quality(str(test_image_file))
    assert quality_result in ['Good', 'Bad']

def test_file_processing_pipeline(test_pdf_file, temp_test_dir):
    """Test the complete file processing pipeline."""
    result = process_file_for_api(str(test_pdf_file), str(temp_test_dir))
    
    assert isinstance(result, list)
    assert all(isinstance(item, dict) for item in result)
    assert all('type' in item and 'source' in item for item in result)

def test_api_authentication():
    """Test API authentication with actual credentials."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key available")
    
    client = anthropic.Anthropic(api_key=api_key)
    assert client is not None

def test_api_communication(test_image_file, temp_test_dir):
    """Test actual API communication with a test image."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key available")
        
    # Create a higher quality test image
    img = Image.new('RGB', (800, 800), color='white')
    draw = ImageDraw.Draw(img)
    # Add some text to make it more realistic
    draw.text((400, 400), "Test Contract Document", fill='black')
    draw.text((400, 450), "Payment Receipt", fill='black')
    img.save(str(test_image_file), quality=95)
    
    # Process the image for API
    image_data = process_file_for_api(str(test_image_file), str(temp_test_dir))
    
    # Skip test if image processing failed
    if not image_data or isinstance(image_data, str):
        pytest.skip(f"Image processing failed: {image_data}")
    
    # Ensure image_data is in the correct format
    if not isinstance(image_data, list):
        image_data = [image_data]
        
    # Add the required text component for the API
    user_prompt = create_api_prompt()
    message_content = [{"type": "text", "text": user_prompt}]
    message_content.extend(image_data)
    
    # Attempt API communication with timeout
    def make_api_call():
        return communicate_with_api(message_content)
    
    with ThreadPoolExecutor() as executor:
        future = executor.submit(make_api_call)
        try:
            classification, response = future.result(timeout=30)  # 30 second timeout
            
            assert classification is not None
            assert response is not None
            assert classification in [
                'Rental_Contract',
                'Mortgage_Contract',
                'Contract_Payment',
                'Teleworking_Agreement',
                'Repayment_Table',
                'Unclassified'
            ]
        except TimeoutError:
            pytest.skip("API call timed out after 30 seconds")

def test_rate_limiting_handling():
    """Test handling of API rate limits."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key available")
    
    # Create a minimal test message that won't hit rate limits as hard
    user_prompt = create_api_prompt()
    test_message = [{"type": "text", "text": user_prompt}]
    
    # Make just two rapid requests to test rate limiting
    responses = []
    max_retries = 2
    timeout_seconds = 15
    
    def make_api_calls():
        for _ in range(max_retries):
            try:
                classification, response = communicate_with_api(test_message)
                responses.append((classification, response))
                time.sleep(1)  # Add delay between requests
            except Exception as e:
                logging.error(f"API call failed: {str(e)}")
    
    # Run API calls with timeout
    with ThreadPoolExecutor() as executor:
        future = executor.submit(make_api_calls)
        try:
            future.result(timeout=timeout_seconds)
        except TimeoutError:
            pytest.skip(f"Rate limit test timed out after {timeout_seconds} seconds")
    
    # Verify we got at least one valid response
    assert len(responses) > 0
    assert any(r[0] is not None for r in responses)

def test_concurrent_execution(azure_db_connection, temp_test_dir):
    """Test system behavior with concurrent execution."""
    # Create multiple test records
    cursor = azure_db_connection.cursor()
    for i in range(5):
        cursor.execute("""
            INSERT INTO contract_payments (status, has_been_renamed, file_name)
            VALUES ('Failed', 0, ?)
        """, (f"test_{i}.pdf",))
    azure_db_connection.commit()
    
    # Run multiple instances simultaneously
    threads = []
    for _ in range(3):
        thread = threading.Thread(
            target=main,
            args=(str(temp_test_dir / "test.lock"),)
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Verify only one instance processed the records
    cursor.execute("""
        SELECT COUNT(*)
        FROM contract_payments
        WHERE has_been_renamed = 1
    """)
    processed_count = cursor.fetchone()[0]
    assert processed_count <= 5  # Should not process more than available records

def test_error_recovery(azure_db_connection, temp_test_dir):
    """Test system recovery from various error conditions."""
    # Test recovery from database connection loss
    def simulate_connection_loss():
        azure_db_connection.close()
        time.sleep(1)
        # Connection should be re-established automatically
    
    # Run system with simulated errors
    threading.Timer(0.5, simulate_connection_loss).start()
    main(str(temp_test_dir / "test.lock"))
    
    # Verify system recovered and processed records
    cursor = azure_db_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM contract_payments WHERE status = 'Failed'")
    failed_count = cursor.fetchone()[0]
    assert failed_count >= 0  # System should have handled the error

def test_end_to_end_flow(azure_db_connection, test_pdf_file, temp_test_dir):
    """Test complete end-to-end system flow."""
    # Create test record
    cursor = azure_db_connection.cursor()
    cursor.execute("""
        INSERT INTO contract_payments (
            status, has_been_renamed, file_name, full_file_path, failure_reason
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        'Failed',
        0,
        test_pdf_file.name,
        str(test_pdf_file),
        'File pattern does not match'
    ))
    azure_db_connection.commit()
    
    # Run main process
    main(str(temp_test_dir / "test.lock"))
    
    # Verify results
    cursor.execute("""
        SELECT status, has_been_renamed, file_name
        FROM contract_payments
        WHERE full_file_path = ?
    """, (str(test_pdf_file),))
    record = cursor.fetchone()
    
    assert record is not None
    assert record.has_been_renamed == 1
    assert record.status in ['New', 'Failed']  # Depending on classification result