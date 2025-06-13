import pytesseract
import cv2
import numpy as np
from PIL import Image
from docx import Document as DocxDocument
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import re
import logging
from typing import Union, List, Optional, Tuple
import os
from pathlib import Path
import platform
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_system_dependencies() -> bool:
    """
    Check if all required system dependencies are installed.
    
    Returns:
        bool: True if all dependencies are installed, False otherwise
    """
    if platform.system() != 'Linux':
        logger.warning("System dependencies check is only supported on Linux")
        return True
        
    required_packages = [
        'tesseract-ocr',
        'libleptonica-dev',
        'libtesseract-dev',
        'poppler-utils'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            subprocess.run(['dpkg', '-s', package], 
                         check=True, 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing system dependencies: {', '.join(missing_packages)}")
        logger.error("Please install them using:")
        logger.error(f"sudo apt-get install -y {' '.join(missing_packages)}")
        return False
        
    return True

def validate_tesseract() -> bool:
    """
    Validate Tesseract installation and Arabic language support.
    
    Returns:
        bool: True if Tesseract is properly configured, False otherwise
    """
    try:
        # Check system dependencies first
        if not check_system_dependencies():
            return False
            
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages()
        
        if 'ara' not in languages:
            logger.error("Arabic language data not found in Tesseract")
            logger.error("Please install it using: sudo apt-get install tesseract-ocr-ara")
            return False
            
        logger.info(f"Tesseract version: {version}, Available languages: {languages}")
        return True
    except Exception as e:
        logger.error(f"Tesseract validation failed: {str(e)}")
        if platform.system() == 'Linux':
            logger.error("Please ensure Tesseract is properly installed:")
            logger.error("sudo apt-get install -y tesseract-ocr tesseract-ocr-ara")
        return False

def clean_arabic_text(text: str) -> str:
    """
    Clean and format Arabic OCR output.
    
    Args:
        text (str): Raw OCR output text
        
    Returns:
        str: Cleaned and formatted text
    """
    if not text:
        return ""
        
    # Remove multiple newlines
    text = re.sub(r'\n\s*\n', ' ', text)
    
    # Remove single newlines that break sentences
    text = re.sub(r'(?<=[.!?])\s*\n', ' ', text)
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove spaces before punctuation
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    
    # Remove spaces after opening brackets and before closing brackets
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text

def preprocess_image(image: Union[str, Image.Image, np.ndarray]) -> np.ndarray:
    """
    Preprocess image for better OCR accuracy.
    
    Args:
        image: Input image (path, PIL Image, or numpy array)
        
    Returns:
        np.ndarray: Preprocessed image
    """
    try:
        # Convert input to numpy array
        if isinstance(image, str):
            img = cv2.imread(image)
            if img is None:
                raise ValueError(f"Could not read image from path: {image}")
        elif isinstance(image, Image.Image):
            img = np.array(image)
        else:
            img = image.copy()
        
        # Convert to grayscale
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        img = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 2
        )
        
        # Denoise
        img = cv2.fastNlMeansDenoising(img)
        
        # Dilate to connect broken characters
        kernel = np.ones((2,2), np.uint8)
        img = cv2.dilate(img, kernel, iterations=1)
        
        return img
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        raise

def extract_text_from_image(image_path: str, lang: str = "ara+eng") -> str:
    """
    Extract text from an image using OCR.
    
    Args:
        image_path (str): Path to the image file
        lang (str): Language(s) for OCR (default: "ara+eng")
        
    Returns:
        str: Extracted and cleaned text
    """
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        # Preprocess image
        img = preprocess_image(image_path)
        
        # Perform OCR
        text = pytesseract.image_to_string(img, lang=lang)
        
        # Clean text if Arabic is included
        if "ara" in lang:
            text = clean_arabic_text(text)
            
        return text
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {str(e)}")
        raise

def extract_text_from_pdf(pdf_path: str, dpi: int = 300, lang: str = "ara+eng") -> Tuple[str, int]:
    """
    Extract text from PDF using OCR for scanned documents.
    
    Args:
        pdf_path (str): Path to the PDF file
        dpi (int): DPI resolution for PDF to image conversion
        lang (str): Language(s) for OCR (default: "ara+eng")
        
    Returns:
        Tuple[str, int]: Extracted and cleaned text from all pages, and number of pages processed
    """
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        # Convert PDF to images
        logger.info(f"Converting PDF to images: {pdf_path}")
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt='png'
        )
        
        total_pages = len(images)
        logger.info(f"Processing {total_pages} pages")
        
        all_text = []
        
        # Process each page
        for i, image in enumerate(images):
            logger.info(f"Processing page {i+1}/{total_pages}")
            
            # Convert PIL Image to numpy array
            img_array = np.array(image)
            
            # Extract text from the page
            text = extract_text_from_image(img_array, lang=lang)
            all_text.append(text)
        
        # Combine all pages
        final_text = ' '.join(all_text)
        
        # Final cleaning if Arabic is included
        if "ara" in lang:
            final_text = clean_arabic_text(final_text)
        
        return final_text, total_pages
        
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        raise

def extract_text_from_word(word_path: str) -> str:
    """
    Extract text from Word document.
    
    Args:
        word_path (str): Path to the Word document
        
    Returns:
        str: Extracted text
    """
    try:
        if not os.path.exists(word_path):
            raise FileNotFoundError(f"Word document not found: {word_path}")
            
        doc = DocxDocument(word_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        logger.error(f"Error processing Word document {word_path}: {str(e)}")
        raise

def test_arabic_ocr(pdf_path: str) -> None:
    """
    Test function to verify Arabic OCR functionality.
    
    Args:
        pdf_path (str): Path to test PDF file
    """
    try:
        # Validate Tesseract installation
        if not validate_tesseract():
            logger.error("Tesseract validation failed. Please check installation.")
            return
            
        # Process PDF
        text, page_count = extract_text_from_pdf(pdf_path, dpi=300, lang="ara")
        
        # Print results
        logger.info(f"Successfully processed {page_count} pages")
        logger.info("First 500 characters of extracted text:")
        logger.info(text[:500])
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

# Example usage
if __name__ == "__main__":
    # Example: Test Arabic OCR
    pdf_path = "path/to/your/arabic.pdf"
    test_arabic_ocr(pdf_path)
