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

def convert_pdf_to_images(pdf_path, save_dir):
    doc = fitz.open(pdf_path)
    images = []
    base_filename = os.path.splitext(os.path.basename(pdf_path))[0]
    save_subdir = os.path.join(save_dir, base_filename)  # Create a subdirectory for each PDF
    os.makedirs(save_subdir, exist_ok=True)  # Ensure the directory exists

    for i, page in enumerate(doc):
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

        # Save images locally
        image_filename = f"{base_filename}_page_{i+1}.jpeg"
        img.save(os.path.join(save_subdir, image_filename))

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

def classify_file(file_path):
    media_type = get_media_type(file_path)
    save_directory = "data/saved_images"  # Define where to save images within the data directory
    os.makedirs(save_directory, exist_ok=True)  # Create directory if it doesn't exist
    if media_type == 'application/pdf':
        images = convert_pdf_to_images(file_path, save_directory)
        images = images[:4]
        image_sources = [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",  # assuming conversion to JPEG
                "data": encode_image_to_base64(image) if image else None
            }
        } for image in images if encode_image_to_base64(image)]
        logging.info(f"Attempting to send {len(image_sources)} images to the API.")
    elif media_type in ['image/jpeg', 'image/png']:
        # Handle JPEG and PNG files directly
        try:
            image_path = os.path.join(save_directory, os.path.basename(file_path))
            with Image.open(file_path) as img:
                # Convert PNG with alpha channel (RGBA) to RGB format for JPEG
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(image_path, format='JPEG')  # Save as JPEG
            encoded_image = encode_image_to_base64(img)
            if encoded_image:
                image_sources = [{
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",  # specify JPEG as we converted to JPEG
                        "data": encoded_image
                    }
                }]
            else:
                logging.error(f"Failed to encode image for file: {file_path}")
                return None, "Failed to encode image"
        except Exception as e:
            logging.error(f"Error processing image file {file_path}: {str(e)}")
            return None, "Error in handling image file"
    else:
        logging.warning(f"Unsupported file type for API processing: {file_path}")
        return None, "Unsupported file type"

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    user_prompt = textwrap.dedent("""\
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

    max_retries = 5
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are an AI administrative assistant. You will be asked a question about documents and you will need to draw a conclusion with the information available to you.",
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}] + image_sources
                }]
            )
            logging.info(f"API Response: {message.content}")
            # Parse the response
            for item in message.content:
                try:
                    response_data = json.loads(item.text)
                    if 'ContentType' in response_data:
                        return response_data['ContentType'], json.dumps(response_data)
                except json.JSONDecodeError:
                    logging.error(f"JSON decoding failed for response: {item.text}")
                    return None, "Failed to decode JSON"
            return None, "No valid ContentType found"
        except RateLimitError as e:
            if e.status_code in [429, 500]:  # Retry on Too Many Requests or Internal Server Error
                wait_time = exponential_backoff(attempt)
                error_type = "Too Many Requests" if e.status_code == 429 else "Internal Server Error"
                logging.info(f"Retrying request to /v1/messages, attempt #{attempt + 1}, in {wait_time} seconds due to {error_type}")
                time.sleep(wait_time)
            else:
                logging.error(f"Error communicating with API: {str(e)}")
                return None, f"API communication error: {str(e)}"
        except APIError as e:  # Catching general API errors
            logging.error(f"General API Error: {str(e)}")
            return None, f"General API communication error: {str(e)}"
        except Exception as e:
            logging.error(f"Unhandled exception: {str(e)}")
            return None, f"Unhandled API communication error: {str(e)}"

    return None, "API request failed after retries"
