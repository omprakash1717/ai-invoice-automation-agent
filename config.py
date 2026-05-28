"""
config.py — Application Configuration
======================================
Loads environment variables and sets up all configuration
values used across the application.
"""

import os
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env file so we can read secrets like GEMINI_API_KEY
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Base directory — points to the project root folder
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Gemini AI Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_MAX_RETRIES = 3          # Number of retry attempts for Gemini calls
GEMINI_RETRY_DELAY = 2          # Base delay (seconds) between retries

# ---------------------------------------------------------------------------
# Tesseract OCR Configuration
# ---------------------------------------------------------------------------
TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# ---------------------------------------------------------------------------
# Flask Configuration
# ---------------------------------------------------------------------------
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "invoice-automation-secret-key-2024")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB max upload size

# ---------------------------------------------------------------------------
# File / Folder Paths
# ---------------------------------------------------------------------------
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")
CSV_FOLDER = os.path.join(BASE_DIR, "csv")
SAMPLE_OUTPUT_FOLDER = os.path.join(BASE_DIR, "sample_output")

# ---------------------------------------------------------------------------
# Allowed Upload Extensions
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "json"}

# ---------------------------------------------------------------------------
# Create required directories if they don't already exist
# ---------------------------------------------------------------------------
for folder in [UPLOAD_FOLDER, LOG_FOLDER, CSV_FOLDER, SAMPLE_OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)
