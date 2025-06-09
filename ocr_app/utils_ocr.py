import pytesseract
import cv2
import numpy as np
from PIL import Image
from docx import Document as DocxDocument
import fitz  # PyMuPDF

def extract_text_from_image(image_path):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 2)
    kernel = np.ones((2,2), np.uint8)
    img = cv2.dilate(img, kernel, iterations=1)
    text = pytesseract.image_to_string(img, lang="ara+eng")
    return text

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyMuPDF (no poppler needed)"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text

def extract_text_from_word(word_path):
    doc = DocxDocument(word_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text
