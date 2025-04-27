import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
from docx import Document as DocxDocument
from PIL import Image

def extract_text_from_image(image_path):
    """Extracts Arabic & English text from an image using Tesseract OCR"""
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Use adaptive thresholding for better contrast
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 2)

    # Dilation to fix broken letters
    kernel = np.ones((2,2), np.uint8)
    img = cv2.dilate(img, kernel, iterations=1)

    text = pytesseract.image_to_string(img, lang="ara+eng")  # ✅ Arabic + English OCR
    return text

def extract_text_from_pdf(pdf_path):
    """Extracts Arabic & English text from a PDF by converting pages to images"""
    images = convert_from_path(pdf_path)
    text = ""
    for image in images:
        img_array = np.array(image)

        # Convert image to grayscale
        img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Adaptive thresholding for better text detection
        img_gray = cv2.adaptiveThreshold(img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 2)

        # Use Arabic + English language model for OCR
        text += pytesseract.image_to_string(img_gray, lang="ara+eng") + "\n"
    
    return text

def extract_text_from_word(word_path):
    """Extracts Arabic & English text from a Word document (.docx)"""
    doc = DocxDocument(word_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text
