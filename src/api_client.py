import time
import anthropic
from anthropic import RateLimitError, APIError
import base64
import json
import os
import logging
from PIL import Image
import io
import fitz  # PyMuPDF
import textwrap

def convert_pdf_to_images(pdf_path, save_dir, max_pages=None):
    """
    Converts the given PDF into images and saves them in the specified directory.
    Only the first `max_pages` pages are converted if `max_pages` is provided.

    Parameters:
        pdf_path (str): The file path to the PDF document.
        save_dir (str): The directory where the images will be saved.
        max_pages (int, optional): The maximum number of pages to convert.

    Returns:
        list: A list of PIL Image objects for the converted pages.
    """
    images = []
    try:
        # Open the PDF file
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            num_pages = total_pages if max_pages is None else min(total_pages, max_pages)
            
            logging.info(f"Total pages in PDF: {total_pages}. Converting the first {num_pages} pages.")

            base_filename = os.path.splitext(os.path.basename(pdf_path))[0]
            save_subdir = os.path.join(save_dir, base_filename)  # Create a subdirectory for each PDF
            os.makedirs(save_subdir, exist_ok=True)  # Ensure the directory exists

            for i in range(num_pages):
                page = doc[i]
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

                # Save images locally
                image_filename = f"{base_filename}_page_{i+1}.jpeg"
                img.save(os.path.join(save_subdir, image_filename))

    except Exception as e:
        print(f"Failed to convert PDF to images due to: {str(e)}")
        return []

    return images

def encode_image_to_base64(image):
    try:
        # Assuming 'image' is already a PIL Image object
        buffered = io.BytesIO()
        # Convert RGBA to RGB if necessary
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        image.save(buffered, format='JPEG')
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return img_base64
    except Exception as e:
        logging.error(f"Error processing image for conversion to base64: {str(e)}")
        return None

def get_media_type(image_path):
    if image_path.lower().endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif image_path.lower().endswith('.png'):
        return 'image/png'
    elif image_path.lower().endswith('.pdf'):
        return 'application/pdf'
    else:
        return None
    
def exponential_backoff(retry_number):
    base_delay = 4   # Initial delay of 1 second
    factor = 2       # Doubling the wait time with each retry
    max_delay = 60   # Maximum delay capped at 60 seconds

    wait_time = min(max_delay, base_delay * (factor ** retry_number))
    return wait_time

def process_file_for_api(file_path, save_directory):
    """
    Processes the file based on its type to prepare for API submission.
    """
    media_type = get_media_type(file_path)
    max_pages=4 # Limit to the first 4 images for processing
    if media_type == 'application/pdf':
        images = convert_pdf_to_images(file_path, save_directory, max_pages)
        images = images[:max_pages]  
        return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encode_image_to_base64(image)}} for image in images if image]
    elif media_type in ['image/jpeg', 'image/png']:
        try:
            final_image_path = os.path.join(save_directory, os.path.basename(file_path))
            with Image.open(file_path) as img:
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(final_image_path, format='JPEG')  # Convert and save as JPEG
            with Image.open(final_image_path) as saved_img:
                return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encode_image_to_base64(saved_img)}}]
        except Exception as e:
            logging.error(f"Error processing image file {file_path}: {str(e)}")
            return []
    else:
        logging.warning(f"Unsupported file type for API processing: {file_path}")
        return []

def communicate_with_api(image_data, retry_limit=5):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = create_api_prompt()

    for attempt in range(retry_limit):
        try:
            response = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are an AI administrative assistant.",
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}] + image_data
                }]
            )
            # Log the full response object to inspect its structure
            logging.info(f"API response received: {response.model_dump_json()}")  # Log the parsed JSON response
            return parse_api_response(response.json())  # Assume response.json() returns a dictionary
        except (RateLimitError, APIError) as e:
            if not handle_api_error(e, attempt):
                return None, "API communication failed after maximum retries"
        except Exception as e:
            logging.error(f"Unexpected error when communicating with API: {str(e)}")
            return None, "Unexpected error in API communication"

def classify_file(file_path):
    """
    Main function to classify a file by processing it and communicating with the API.
    """
    save_directory = "data/saved_images"
    os.makedirs(save_directory, exist_ok=True)
    absolute_file_path = os.path.abspath(file_path)  # Secure file path handling

    image_data = process_file_for_api(absolute_file_path, save_directory)
    if not image_data:
        return None, "Failed to process image data or unsupported file type"

    classification, response = communicate_with_api(image_data)
    if classification:
        return classification, response
    else:
        return None, "API communication failed or no valid response"

def handle_api_error(e, attempt):
    wait_time = exponential_backoff(attempt)
    logging.error(f"Error communicating with API on attempt {attempt + 1}: {str(e)}")
    time.sleep(wait_time)
    if attempt >= 4:  # Last attempt
        return False  # Indicates no more retries
    return True

def parse_api_response(response_data):
    try:
        if isinstance(response_data, str):
            response_data = json.loads(response_data)

        if 'content' in response_data and isinstance(response_data['content'], list) and response_data['content']:
            content_text = response_data['content'][0].get('text', '')
            content_data = json.loads(content_text)
            return content_data.get('ContentType'), json.dumps(content_data)
        return None, "Content field missing or improperly formatted"
    except Exception as e:
        return None, f"Failed to parse API response: {e}"

def create_api_prompt():
    return textwrap.dedent("""\
        You are an AI administrative assistant that is tasked with changing the file name
        in accordance with the content of the file. The current filename may not be accurate so make sure to check the content.

        The content type could be one of the following: Rental Contract, Mortgage Contract, Contract Payment,
        Teleworking Agreement, Unclassified.

        To mark a file as a Rental/Mortgage contract it must contain at least 1 page from said contract.

        For more context, if you see a payment being made (whether for rental or mortgage) you need to mark it as Contract Payment.

        If the image doesn't seem to encapsulate the above, classify as Unclassified.

        So you will put the content type in the value of ContentType.

        You will be responding to this message with JSON in the following format:

        {
            "ContentType": ""
        }

        The images will likely contain French/Dutch/English.
    """)