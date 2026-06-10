"""
extractor.py — Gemini AI Integration & Data Extraction
=======================================================
Sends extracted invoice text to Google Gemini and parses
the structured JSON response.  Includes retry logic,
JSON sanitisation, and schema validation.

Uses the new google-genai SDK (v2+).
"""

import json
import time

from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_RETRIES, GEMINI_RETRY_DELAY
from logger import log_api, log_error
from utils import sanitize_json, validate_invoice_data, get_file_extension

# ---------------------------------------------------------------------------
# Configure Gemini client
# ---------------------------------------------------------------------------
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Prompt Template
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are an intelligent invoice extraction AI.
Analyze the attached invoice file carefully and return ONLY valid JSON.

Requirements:
- No markdown formatting
- No explanations or extra text
- Strict JSON only
- Use null for any missing values
- confidence_score should be between 0 and 1

Return this exact JSON schema:
{{
  "document_type": "standard_invoice | credit_note | unknown",
  "vendor_name": "string or null",
  "invoice_number": "string or null",
  "invoice_date": "string (YYYY-MM-DD) or null",
  "total_amount": number or 0,
  "line_items": [
    {{
      "description": "string",
      "quantity": number,
      "unit_price": number,
      "amount": number
    }}
  ],
  "confidence_score": number between 0 and 1
}}"""


# ---------------------------------------------------------------------------
# Main Extraction Function
# ---------------------------------------------------------------------------

def extract_invoice_data(filename: str = "unknown", filepath: str = None) -> dict:
    """
    Send invoice file to Gemini natively and return validated, structured data.

    Implements:
      - Native Gemini Multimodal file upload
      - Retry with exponential back-off (up to GEMINI_MAX_RETRIES)
      - JSON sanitisation (strip markdown fences, trailing commas, etc.)
      - Schema validation with fallback defaults

    Args:
        filename: Original filename (used for logging).
        filepath: Absolute path to the file on disk.

    Returns:
        dict with validated invoice fields, plus a "status" key
        ("success", "partial", or "failed").
    """
    # Guard: no API key configured
    if not GEMINI_API_KEY or client is None:
        log_error(filename, "gemini_api", "GEMINI_API_KEY not configured")
        return _failed_result(filename, "GEMINI_API_KEY not configured in .env file")

    if not filepath:
        log_error(filename, "gemini_api", "No filepath provided")
        return _failed_result(filename, "No file path provided")

    uploaded_file = None
    try:
        log_api(filename, "upload", "pending", "Uploading file to Gemini")
        uploaded_file = client.files.upload(file=filepath)
    except Exception as e:
        log_error(filename, "gemini_api", f"Failed to upload file: {e}")
        return _failed_result(filename, f"Failed to upload file to Gemini: {e}")

    contents = [EXTRACTION_PROMPT, uploaded_file]

    # Retry loop
    last_error = ""
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            # Use the new google-genai SDK client
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )

            # Extract text from response
            raw = response.text
            if not raw:
                raise ValueError("Empty response from Gemini")

            # Sanitise & parse JSON
            clean = sanitize_json(raw)
            data = json.loads(clean)

            # Validate against schema
            validated = validate_invoice_data(data)

            # Determine status
            status = "success"
            if validated["vendor_name"] is None and validated["invoice_number"] is None:
                status = "partial"

            validated["status"] = status
            validated["raw_response"] = raw[:2000]  # keep a snippet for debugging

            log_api(filename, GEMINI_MODEL, status, "Extraction successful")
            return validated

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            log_api(filename, GEMINI_MODEL, "retry",
                    f"Attempt {attempt} JSON error: {e}")
            is_rate_limit = False

        except Exception as e:
            last_error = str(e)
            log_api(filename, GEMINI_MODEL, "retry",
                    f"Attempt {attempt} error: {e}")
            
            # Identify if it's a transient rate limit vs permanent
            is_rate_limit = "429" in last_error or "RESOURCE_EXHAUSTED" in last_error
            is_permanent = "API_KEY_INVALID" in last_error.upper() or "GenerateRequestsPerDay" in last_error or "limit: 20" in last_error.lower()
            
            if is_permanent:
                log_error(filename, "gemini_api", f"Permanent API error/quota reached: {last_error}")
                break

        # Exponential back-off before next retry
        if attempt < GEMINI_MAX_RETRIES:
            import re
            import random
            
            sleep_time = GEMINI_RETRY_DELAY * attempt
            
            if locals().get("is_rate_limit", False):
                # Try to parse the exact retry time from the error message
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", last_error)
                if match:
                    sleep_time = float(match.group(1)) + 1.0 # add 1s buffer
                else:
                    sleep_time = max(sleep_time, 15)
                
                # Add a random jitter
                sleep_time += random.uniform(1.0, 3.0)

            time.sleep(sleep_time)

    # Clean up the uploaded file on Gemini servers
    if uploaded_file:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

    # All retries exhausted
    log_error(filename, "gemini_api", f"All {GEMINI_MAX_RETRIES} attempts failed: {last_error}")
    return _failed_result(filename, last_error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _failed_result(filename: str, error: str) -> dict:
    """Return a default result dict with status='failed'."""
    return {
        "document_type": "unknown",
        "vendor_name": None,
        "invoice_number": None,
        "invoice_date": None,
        "total_amount": 0,
        "line_items": [],
        "confidence_score": 0,
        "status": "failed",
        "error": error,
    }
