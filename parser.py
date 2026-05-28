"""
parser.py — OCR & PDF Text Extraction
======================================
Extracts raw text from uploaded invoices.
  - PDF files  → pdfplumber
  - Image files → pytesseract + Pillow (with preprocessing)
"""

import os

# PDF parsing
import pdfplumber

# Image OCR
from PIL import Image, ImageFilter, ImageEnhance

# Try importing pytesseract — it's optional (requires Tesseract installed)
try:
    import pytesseract
    from config import TESSERACT_PATH
    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from logger import log_ocr, log_error
from utils import get_file_extension


# ---------------------------------------------------------------------------
# PDF Extraction (pdfplumber)
# ---------------------------------------------------------------------------

def parse_pdf(filepath: str) -> str:
    """
    Extract text from every page of a PDF file using pdfplumber.

    Args:
        filepath: Absolute path to the PDF file.

    Returns:
        Combined text from all pages, or empty string on failure.
    """
    text_parts = []

    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        combined = "\n".join(text_parts)
        filename = os.path.basename(filepath)

        if combined.strip():
            log_ocr(filename, "pdfplumber", len(combined), "success")
        else:
            log_ocr(filename, "pdfplumber", 0, "empty")

        return combined

    except Exception as e:
        filename = os.path.basename(filepath)
        log_error(filename, "pdf_parsing", str(e))
        log_ocr(filename, "pdfplumber", 0, "failed")
        return ""


# ---------------------------------------------------------------------------
# Image Preprocessing (improves OCR accuracy)
# ---------------------------------------------------------------------------

def _preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing steps to improve OCR accuracy:
      1. Convert to grayscale
      2. Increase contrast
      3. Apply slight sharpening
      4. Resize if too small

    Args:
        image: PIL Image object.

    Returns:
        Preprocessed PIL Image.
    """
    # Convert to grayscale
    image = image.convert("L")

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    # Sharpen
    image = image.filter(ImageFilter.SHARPEN)

    # Up-scale small images for better OCR
    width, height = image.size
    if width < 1000:
        scale = 1000 / width
        image = image.resize(
            (int(width * scale), int(height * scale)),
            Image.LANCZOS,
        )

    return image


# ---------------------------------------------------------------------------
# Image OCR (pytesseract)
# ---------------------------------------------------------------------------

def parse_image(filepath: str) -> str:
    """
    Extract text from a JPG/PNG image using Tesseract OCR.

    The image is preprocessed (grayscale, contrast, sharpen) before OCR
    to improve accuracy.

    Args:
        filepath: Absolute path to the image file.

    Returns:
        Extracted text, or empty string on failure.
    """
    filename = os.path.basename(filepath)

    if not TESSERACT_AVAILABLE:
        log_error(filename, "image_ocr", "pytesseract not installed or Tesseract not found")
        return ""

    try:
        image = Image.open(filepath)
        processed = _preprocess_image(image)

        # Run OCR
        text = pytesseract.image_to_string(processed, lang="eng")

        if text.strip():
            log_ocr(filename, "pytesseract", len(text), "success")
        else:
            log_ocr(filename, "pytesseract", 0, "empty")

        return text

    except Exception as e:
        log_error(filename, "image_ocr", str(e))
        log_ocr(filename, "pytesseract", 0, "failed")
        return ""


# ---------------------------------------------------------------------------
# Unified Entry Point
# ---------------------------------------------------------------------------

def parse_file(filepath: str) -> str:
    """
    Detect file type and route to the appropriate parser.

    Supported:
      - .pdf       → parse_pdf()
      - .jpg/.jpeg/.png → parse_image()

    Args:
        filepath: Absolute path to the uploaded file.

    Returns:
        Extracted text string.
    """
    ext = get_file_extension(filepath)

    if ext == "pdf":
        return parse_pdf(filepath)
    elif ext in ("jpg", "jpeg", "png"):
        return parse_image(filepath)
    else:
        filename = os.path.basename(filepath)
        log_error(filename, "parsing", f"Unsupported file type: .{ext}")
        return ""
