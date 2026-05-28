"""
logger.py — Centralized Logging System
=======================================
Provides structured logging functions for every stage of the
invoice processing pipeline.  All logs are written to the /logs folder.
"""

import os
import json
import threading
from datetime import datetime
from config import LOG_FOLDER

# ---------------------------------------------------------------------------
# Helper — write a log entry to a specific log file
# ---------------------------------------------------------------------------

_log_lock = threading.Lock()

def _write_log(filename: str, entry: dict):
    """
    Append a timestamped JSON log entry to the specified log file.

    Args:
        filename: Name of the log file (e.g. "processing.log")
        entry:    Dictionary with log data
    """
    filepath = os.path.join(LOG_FOLDER, filename)
    entry["timestamp"] = datetime.now().isoformat()

    try:
        with _log_lock:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # Last-resort fallback — print to console so we never silently lose info
        print(f"[LOGGER ERROR] Could not write to {filepath}: {e}")


# ---------------------------------------------------------------------------
# Public Logging Functions
# ---------------------------------------------------------------------------

def log_processing(filename: str, status: str, message: str, data: dict = None):
    """Log a general processing event (upload accepted, pipeline started, etc.)."""
    _write_log("processing.log", {
        "type": "processing",
        "filename": filename,
        "status": status,
        "message": message,
        "data": data or {},
    })


def log_routing(filename: str, route: str, amount: float, status: str):
    """Log the routing decision made for an invoice."""
    _write_log("routing.log", {
        "type": "routing",
        "filename": filename,
        "route": route,
        "amount": amount,
        "status": status,
    })


def log_error(filename: str, stage: str, error: str):
    """Log a failure that occurred during any pipeline stage."""
    _write_log("failed.log", {
        "type": "error",
        "filename": filename,
        "stage": stage,
        "error": error,
    })


def log_ocr(filename: str, method: str, chars_extracted: int, status: str):
    """Log OCR / text-extraction results."""
    _write_log("ocr.log", {
        "type": "ocr",
        "filename": filename,
        "method": method,
        "chars_extracted": chars_extracted,
        "status": status,
    })


def log_api(filename: str, model: str, status: str, message: str = ""):
    """Log Gemini API call results."""
    _write_log("api.log", {
        "type": "api",
        "filename": filename,
        "model": model,
        "status": status,
        "message": message,
    })


# ---------------------------------------------------------------------------
# Read logs back (used by the GET /logs endpoint)
# ---------------------------------------------------------------------------

def read_logs(log_type: str = "processing", limit: int = 100) -> list:
    """
    Read the most recent *limit* entries from the specified log file.

    Args:
        log_type: One of "processing", "routing", "failed", "ocr", "api"
        limit:    Maximum number of entries to return

    Returns:
        List of log-entry dicts, newest first.
    """
    filepath = os.path.join(LOG_FOLDER, f"{log_type}.log")

    if not os.path.exists(filepath):
        return []

    entries = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    # Return newest first, capped at limit
    return list(reversed(entries[-limit:]))
