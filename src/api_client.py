"""
api_client.py

This module is dedicated to managing the communication and data transformation with external APIs.
It includes functionalities for converting PDFs to images, performing image quality assessments,
encoding images to base64, adjusting retries on API limit hits, and other necessary tasks
to prepare and handle data for API interactions. It integrates robust error handling mechanisms
to ensure reliable operation under various conditions.
"""

import time
import anthropic
from anthropic import RateLimitError, APIError
import base64
import json
import os
import logging
from PIL import Image
import pytesseract
import io
import fitz  # PyMuPDF
import textwrap
import cv2
import numpy as np
import re

def check_focus_measure(gray_image):
    """
    Checks the focus measure of a grayscale image using the Laplacian variance method.

    Args:
        gray_image (numpy.ndarray): Grayscale image as a NumPy array.

    Returns:
        str: 'Good' if the focus measure is above the threshold, 'Bad' otherwise.
    """
    focus_measure = cv2.Laplacian(gray_image, cv2.CV_64F).var()
    logging.info(f"Focus measure: {focus_measure}")
    return 'Good' if focus_measure >= 100 else 'Bad'  # Assuming 100 is the threshold

def check_histogram_spread(gray_image):
    """
    Checks the histogram spread of a grayscale image using the coefficient of variation.

    Args:
        gray_image (numpy.ndarray): Grayscale image as a NumPy array.

    Returns:
        str: 'Good' if the histogram spread is above the threshold, 'Bad' otherwise.
    """
    # Calculate histogram
    hist = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
    # Normalize the histogram
    hist_norm = hist.ravel() / hist.max()
    # Calculate the spread using the coefficient of variation
    hist_spread = np.std(hist_norm) / np.mean(hist_norm)
    logging.info(f"Histogram spread: {hist_spread}")
    return 'Good' if hist_spread > 0.5 else 'Bad'  # Threshold can be adjusted

def check_ocr_confidence(image_path):
    """
    Checks the OCR confidence of an image using Tesseract OCR.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: 'Good' if the average OCR confidence is above the threshold, 'Bad' otherwise.
    """
    # Load the image with Pillow
    image = Image.open(image_path)
    # Perform OCR using Tesseract
    ocr_result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    # Calculate average confidence
    confidences = [int(conf) for conf in ocr_result['conf'] if conf != '-1']
    average_confidence = sum(confidences) / len(confidences) if confidences else 0
    logging.info(f"Average OCR confidence: {average_confidence}")
    return 'Good' if average_confidence >= 10 else 'Bad'  # Threshold can be adjusted

def check_image_quality(image_path):
    """
    Checks the overall quality of an image based on focus measure, histogram spread, and OCR confidence.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: 'Good' if all quality measures are above their respective thresholds, 'Bad' otherwise.
    """
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    focus = check_focus_measure(gray)
    histogram = check_histogram_spread(gray)
    ocr_confidence = check_ocr_confidence(image_path)
    
    results = {
        "Focus Measure": focus,
        "Histogram Spread": histogram,
        "OCR Confidence": ocr_confidence
    }
    
    logging.info(f"Image quality results: {results}")
    
    # Combine the results
    if 'Bad' in results.values():
        return 'Bad'
    else:
        return 'Good'

def convert_pdf_to_images(pdf_path, save_dir, max_pages=None):
    """
    Converts a PDF file to a series of images and saves them locally.

    Args:
        pdf_path (str): The path to the PDF file.
        save_dir (str): The directory where converted images will be stored.
        max_pages (int, optional): Maximum number of pages to convert. Defaults to None.

    Returns:
        List[PIL.Image]: A list of PIL Image objects of the converted pages.
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
    """
    Encodes a PIL Image object to a base64 string.

    Args:
        image (PIL.Image): Image object to be encoded.

    Returns:
        str: Base64 encoded string of the image, or None if an error occurs.
    """
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
    """
    Determines the media type (MIME type) based on the file extension.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Media type (e.g., 'image/jpeg', 'image/png', 'application/pdf'), or None if unsupported.
    """
    if image_path.lower().endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif image_path.lower().endswith('.png'):
        return 'image/png'
    elif image_path.lower().endswith('.pdf'):
        return 'application/pdf'
    else:
        return None

def save_image_as_jpeg(image, file_path):
    """
    Saves a PIL Image in JPEG format, converting RGBA to RGB if necessary.

    Args:
        image (PIL.Image): The image to be saved.
        file_path (str): Full path where the image will be saved.
    """
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    image.save(file_path, format='JPEG')


def exponential_backoff(retry_number):
    """
    Calculates the exponential backoff time based on the retry number.

    Args:
        retry_number (int): The current retry attempt number.

    Returns:
        float: The calculated wait time in seconds.
    """
    base_delay = 6   # Initial delay of 1 second
    factor = 2       # Doubling the wait time with each retry
    max_delay = 60   # Maximum delay capped at 60 seconds

    wait_time = min(max_delay, base_delay * (factor ** retry_number))
    return wait_time

def process_file_for_api(file_path, save_directory):
    """
    Processes the file based on its type to prepare for API submission.

    Args:
        file_path (str): Path to the file to be processed.
        save_directory (str): Directory where processed files will be saved.

    Returns:
        Union[List[dict], str]: A list of dictionaries containing image data ready for API submission,
                                or a string indicating poor image quality or an empty list if processing fails.
    """
    logging.info(f"Start processing file: {os.path.basename(file_path)}")
    media_type = get_media_type(file_path)
    max_pages = 4  # Limit to the first 4 images for processing

    if media_type == 'application/pdf':
        images = convert_pdf_to_images(file_path, save_directory, max_pages)
        images = images[:max_pages]
        image_data = []
        poor_quality_count = 0  # To track how many images are classified as poor quality

        for index, image in enumerate(images):
            final_image_path = os.path.join(save_directory, f"temp_image_{index}.jpeg")
            save_image_as_jpeg(image, final_image_path)
            quality = check_image_quality(final_image_path)
            if quality == 'Bad':
                logging.warning(f"Low quality PDF page found, this page will not be sent to the API")
                poor_quality_count += 1
            else:
                image_data.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encode_image_to_base64(image)}})

        if poor_quality_count == len(images):
            return "Unclassified - Poor image quality"
        return image_data

    elif media_type in ['image/jpeg', 'image/png']:
        try:
            final_image_path = os.path.join(save_directory, os.path.basename(file_path))
            with Image.open(file_path) as img:
                save_image_as_jpeg(img, final_image_path)
            quality = check_image_quality(final_image_path)
            if quality == 'Bad':
                return "Unclassified - Poor image quality"
            else:
                with Image.open(final_image_path) as saved_img:
                    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encode_image_to_base64(saved_img)}}]
        except Exception as e:
            logging.error(f"Error processing image file {file_path}: {str(e)}")
            return []
    else:
        logging.warning(f"Unsupported file type for API processing: {file_path}")
        return []


def communicate_with_api(image_data, retry_limit=5):
    """
    Communicates with an external API to classify images, handling retries and rate limits.

    Args:
        image_data (list): Encoded image data ready for API submission.
        retry_limit (int): Maximum number of retry attempts in case of API errors.

    Returns:
        Tuple[str, str]: A tuple containing the classification result and API response,
                         or None and an error message if communication fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = create_api_prompt()

    for attempt in range(retry_limit):
        try:
            response = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are an AI administrative assistant. You process documents in the context of the Belgian Mobility Budget.",
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}] + image_data
                }]
            )
            # Log the full response object to inspect its structure
            logging.info(f"API response received: {response.model_dump_json()}")  # Log the parsed JSON response
            return parse_api_response(response.model_dump_json())  # Assume response.json() returns a dictionary
        except (RateLimitError, APIError) as e:
            if not handle_api_error(e, attempt):
                return None, "API communication failed after maximum retries"
        except Exception as e:
            logging.error(f"Unexpected error when communicating with API: {str(e)}")
            return None, "Unexpected error in API communication"

def classify_file(file_path):
    """
    Main function to classify a file by processing it and communicating with the API.

    Args:
        file_path (str): Path to the file to be classified.

    Returns:
        Tuple[str, str]: A tuple containing the classification result and API response,
                         or None and an error message if classification fails.
    """
    save_directory = "data/saved_images"
    os.makedirs(save_directory, exist_ok=True)
    absolute_file_path = os.path.abspath(file_path)  # Secure file path handling

    image_data = process_file_for_api(absolute_file_path, save_directory)
    if not image_data:
        return None, "Failed to process image data or unsupported file type"
    elif image_data == 'Unclassified - Poor image quality':
        return 'Unclassified - Poor image quality', None
    
    classification, response = communicate_with_api(image_data)
    if classification:
        return classification, response
    else:
        return None, "API communication failed or no valid response"

def handle_api_error(e, attempt):
    """
    Handles API errors by applying exponential backoff and logging the error.

    Args:
        e (Exception): The exception object representing the API error.
        attempt (int): The current retry attempt number.

    Returns:
        bool: True if retrying should continue, False if the maximum number of retries is reached.
    """
    wait_time = exponential_backoff(attempt)
    logging.error(f"Error communicating with API on attempt {attempt + 1}: {str(e)}")
    time.sleep(wait_time)
    if attempt >= 4:  # Last attempt
        return False  # Indicates no more retries
    return True

def parse_api_response(response_data):
    """
    Parses the API response data to extract the content type and JSON data.

    Args:
        response_data (Union[str, dict]): The API response data as a string or dictionary.

    Returns:
        Tuple[str, str]: A tuple containing the content type and JSON data,
                         or None and an error message if parsing fails.
    """
    try:
        if isinstance(response_data, str):
            logging.info(f"Response data is string. Attempting to load as JSON: {response_data}")
            response_data = json.loads(response_data)

        if 'content' in response_data and isinstance(response_data['content'], list) and response_data['content']:
            content_text = response_data['content'][0].get('text', '')
            logging.info(f"Extracted content text: {content_text}")
            # Preprocess the content_text to remove any unwanted control characters
            clean_content_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content_text)
            # Now attempt to load the cleaned text as JSON
            content_data = json.loads(clean_content_text)
            logging.info(f"Extracted ContentType: {content_data.get('ContentType')}")
            return content_data.get('ContentType'), json.dumps(content_data)
        return None, "Content field missing or improperly formatted"
    except Exception as e:
        logging.info(f"Failed to parse API response: {e}")
        return None, f"Failed to parse API response: {e}"

def create_api_prompt():
    """
    Creates the API prompt for image classification.

    Returns:
        str: The API prompt as a string.
    """
    return textwrap.dedent("""\
        You are an AI administrative assistant that is tasked with changing the file name
        in accordance with the content of the file. The current filename may not be accurate, so make sure to thoroughly review the content, paying close attention to the document title, parties involved, and key terms and clauses.
        You are only given the first 1-4 pages of the document.
        The content type could be one of the following: Rental_Contract, Mortgage_Contract, Contract_Payment,
        Teleworking_Agreement, Repayment_Table, Unclassified.
        Some information and rules:
        - To mark a file as a Rental/Mortgage contract it must contain at least 1 page from said contract or contains information very similar to a contract(Lender, credit intermediary, Renter, Owner).
        - Mortgage Contract: A legal agreement between a borrower and a lender where the borrower receives funds to purchase a property and agrees to pay back the loan over a period, typically with interest. The property serves as collateral for the loan.
        - Rental Contract: A legal document that outlines the terms and conditions under which one party agrees to rent property owned by another party. It specifies rental payments, duration of the rental, and other terms such as maintenance responsibilities.
        - Contract Payment: If you see a payment being made (whether for rental or mortgage) you need to mark it as Contract Payment.
        there needs to be a bankstatement or some kind or a signed receipt.
        - Teleworking Agreement: An agreement between an employer and an employee that outlines the terms under which the employee can work from locations other than the employer's office, often including home. It covers aspects like work hours, communication methods, and equipment usage.
        - Repayment Table (Amortization Schedule): It almost exclusively contains a Mortgage Repayment Table (Principal, interest, etc).
        - If the image doesn't seem to encapsulate the above, classify as Unclassified.

        Your thought process should be a step-by-step analysis of the document's content, and you should only provide the conclusion about the content type at the end of your response.
        So you will put the content type in the value of ContentType.
        You will be responding to this message with JSON in the following format:
        {
            "ThoughtProcess": "",
            "ContentType": ""
        }
        The images will likely contain French/Dutch/English.
    """)