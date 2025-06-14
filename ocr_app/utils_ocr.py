import pytesseract
import cv2
import numpy as np
from PIL import Image
from docx import Document as DocxDocument
import fitz  # PyMuPDF
import re
from urllib.parse import unquote


def extract_text_from_image(image_path):
    """Enhanced OCR for Arabic text with specialized preprocessing"""
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            return ""
        
        # Convert to LAB color space - better for Arabic text
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        
        # Merge enhanced L-channel with original A and B channels
        limg = cv2.merge((cl, a, b))
        
        # Convert back to BGR then to grayscale
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding with Arabic text optimization
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 41, 2
        )
        
        # Gentle noise removal
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Custom Tesseract config for Arabic
        custom_config = r'-l ara+eng --psm 6 -c preserve_interword_spaces=1'
        
        # Perform OCR with Arabic/English support
        text = pytesseract.image_to_string(cleaned, config=custom_config)
        
        return text
    
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    """Enhanced PDF extraction with Arabic text preservation"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            # Use flags to preserve Arabic ligatures and formatting
            text += page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE) + "\n"
        return text
    except Exception as e:
        print(f"PDF Extraction Error: {e}")
        return ""

def extract_text_from_word(word_path):
    """Extract text from Word documents with Arabic support"""
    try:
        doc = DocxDocument(word_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Word Extraction Error: {e}")
        return ""

# Text normalization function with Arabic character preservation
def advanced_normalize_text(text):
    """Arabic text normalization with special character preservation"""
    if not text:
        return ""
    
    # Multiple URL decoding attempts
    for _ in range(3):
        try:
            if '%' in text:
                decoded = unquote(text)
                if decoded != text:
                    text = decoded
                else:
                    break
        except:
            break
    
    # Extended Arabic diacritics removal
    text = re.sub(r'[\u064B-\u0652\u0670\u0640\u06D6-\u06ED\u08F0-\u08FF]', '', text)
    
    # Comprehensive Arabic letter normalizations
    arabic_normalizations = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
        'ة': 'ه', 'ت': 'ت',
        'ى': 'ي', 'ئ': 'ي', 'ؤ': 'و',
        'ه': 'ه', 'ة': 'ه',
        'ك': 'ك', 'ی': 'ي', 'ے': 'ي',
        '\u200c': '', '\u200d': '', '\u200e': '', '\u200f': '',
    }
    
    for old_char, new_char in arabic_normalizations.items():
        text = text.replace(old_char, new_char)
    
    # Convert to lowercase
    text = text.lower()
    
    # Preserve underscores and hyphens in Arabic phrases
    # Convert only other separators to spaces
    text = re.sub(r'[\|/\\]+', ' ', text)
    
    # Remove extra punctuation but preserve Arabic-English-numbers
    # Keep underscores and hyphens for phrase matching
    text = re.sub(r'[^\w\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF_-]', ' ', text)
    
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
