"""
utils.py — Utility Functions
=============================
Reusable helper functions used across the application:
file validation, ID generation, JSON sanitisation, schema
validation, and formatting.
"""

import re
import uuid
import json
from datetime import datetime
from config import ALLOWED_EXTENSIONS

# ---------------------------------------------------------------------------
# File Validation
# ---------------------------------------------------------------------------

def validate_file(filename: str) -> bool:
    """
    Check whether the uploaded file has an allowed extension.

    Args:
        filename: Original name of the uploaded file.

    Returns:
        True if the extension is in ALLOWED_EXTENSIONS, else False.
    """
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """Return the lowercase extension of a filename (without the dot)."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """Generate a short unique ID for each processing job."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# JSON Sanitisation
# ---------------------------------------------------------------------------

def sanitize_json(text: str) -> str:
    """
    Clean raw AI response text so it can be parsed as JSON.

    Common issues handled:
      - Markdown code fences (```json ... ```)
      - Leading/trailing whitespace
      - BOM characters
      - Trailing commas before closing braces/brackets
    """
    if not text:
        return "{}"

    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)

    # Remove BOM and extra whitespace
    text = text.strip().lstrip("\ufeff")

    # Remove trailing commas (e.g.  , } or , ])
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


# ---------------------------------------------------------------------------
# Invoice Data Validation
# ---------------------------------------------------------------------------

# Required fields and their default fallback values
_SCHEMA_DEFAULTS = {
    "document_type": "unknown",
    "vendor_name": None,
    "invoice_number": None,
    "invoice_date": None,
    "total_amount": 0,
    "line_items": [],
    "confidence_score": 0,
}


def validate_invoice_data(data: dict) -> dict:
    """
    Ensure the extracted invoice data has all required fields.
    Missing fields are filled with sensible defaults.

    Also normalises total_amount to a float and clamps
    confidence_score between 0 and 1.

    Args:
        data: Raw parsed dict from Gemini response.

    Returns:
        Validated & normalised dict.
    """
    validated = {}

    for key, default in _SCHEMA_DEFAULTS.items():
        validated[key] = data.get(key, default)

    # --- Normalise total_amount to float and ensure positive ---
    try:
        amount = validated["total_amount"]
        if isinstance(amount, str):
            # Remove currency symbols & commas
            amount = re.sub(r"[^\d.\-]", "", amount)
        validated["total_amount"] = abs(float(amount)) if amount else 0.0
    except (ValueError, TypeError):
        validated["total_amount"] = 0.0

    # --- Clamp confidence_score ---
    try:
        score = float(validated["confidence_score"])
        validated["confidence_score"] = max(0.0, min(1.0, score))
    except (ValueError, TypeError):
        validated["confidence_score"] = 0.0

    # --- Validate document_type ---
    valid_types = {"standard_invoice", "credit_note", "unknown"}
    if validated["document_type"] not in valid_types:
        validated["document_type"] = "unknown"

    # --- Ensure line_items is a list and sanitize numbers to positive ---
    if isinstance(validated["line_items"], list):
        sanitized_items = []
        for item in validated["line_items"]:
            if isinstance(item, dict):
                # Ensure fields are absolute/positive values
                for num_field in ["quantity", "unit_price", "amount"]:
                    if num_field in item and item[num_field] is not None:
                        try:
                            val = item[num_field]
                            if isinstance(val, str):
                                val = re.sub(r"[^\d.\-]", "", val)
                            item[num_field] = abs(float(val))
                        except (ValueError, TypeError):
                            item[num_field] = 0.0
                sanitized_items.append(item)
        validated["line_items"] = sanitized_items
    else:
        validated["line_items"] = []

    return validated


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_currency(amount) -> str:
    """Format a number as a currency string (e.g. ₹1,23,456.78)."""
    try:
        return f"₹{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"


def format_timestamp() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.utcnow().isoformat() + "Z"
