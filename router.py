"""
router.py — Invoice Routing Logic
===================================
Decides where each processed invoice should go based on its
total_amount and document_type:

  • amount > 50,000  → "High Value" route  (+ simulated Slack alert)
  • amount <= 50,000 → Append to invoices.csv
  • type == unknown  → Append to human_review.log
"""

import os
import csv
import json
from datetime import datetime

from config import CSV_FOLDER, LOG_FOLDER
from logger import log_routing, log_error


# ---------------------------------------------------------------------------
# CSV Helper
# ---------------------------------------------------------------------------

CSV_HEADERS = [
    "timestamp",
    "filename",
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "total_amount",
    "document_type",
    "confidence_score",
    "route",
]


def _append_to_csv(row: dict):
    """Append a single row to csv/invoices.csv, creating the file if needed."""
    filepath = os.path.join(CSV_FOLDER, "invoices.csv")
    file_exists = os.path.exists(filepath)

    try:
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        log_error(row.get("filename", "unknown"), "csv_write", str(e))


# ---------------------------------------------------------------------------
# Human Review Helper
# ---------------------------------------------------------------------------

def _append_to_human_review(filename: str, data: dict):
    """Append an entry to logs/human_review.log for manual inspection."""
    filepath = os.path.join(LOG_FOLDER, "human_review.log")
    entry = {
        "timestamp": datetime.now().isoformat(),
        "filename": filename,
        "reason": "Unknown document type or extraction failure",
        "data": data,
    }
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log_error(filename, "human_review_write", str(e))


# ---------------------------------------------------------------------------
# Simulated Slack Notification
# ---------------------------------------------------------------------------

def _simulate_slack_notification(filename: str, amount: float, vendor: str):
    """
    Simulate sending a Slack alert for high-value invoices.
    In production this would call the Slack API; here we just log it.
    """
    message = (
        f"🚨 HIGH VALUE INVOICE ALERT 🚨\n"
        f"File:   {filename}\n"
        f"Vendor: {vendor or 'Unknown'}\n"
        f"Amount: ₹{amount:,.2f}\n"
        f"Time:   {datetime.now().isoformat()}"
    )
    # Write to a dedicated Slack log so the frontend can show it
    slack_log = os.path.join(LOG_FOLDER, "slack_notifications.log")
    try:
        with open(slack_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "filename": filename,
                "amount": amount,
                "vendor": vendor,
                "message": message,
            }) + "\n")
    except Exception:
        pass

    print(f"\n{'='*50}")
    print(message)
    print(f"{'='*50}\n")

    return message


# ---------------------------------------------------------------------------
# Main Routing Function
# ---------------------------------------------------------------------------

def route_invoice(data: dict, filename: str) -> dict:
    """
    Apply routing logic to a processed invoice.

    Rules:
      1. total_amount > 50,000        → High Value route + Slack alert
      2. total_amount <= 50,000       → Save to CSV
      3. document_type == "unknown"   → Human review queue

    Args:
        data:     Validated invoice data dict from extractor.
        filename: Original uploaded filename.

    Returns:
        dict with routing result information.
    """
    amount = data.get("total_amount", 0)
    doc_type = data.get("document_type", "unknown")
    vendor = data.get("vendor_name", "Unknown")
    status = data.get("status", "failed")
    timestamp = datetime.now().isoformat()

    # Build a CSV-compatible row
    csv_row = {
        "timestamp": timestamp,
        "filename": filename,
        "vendor_name": vendor,
        "invoice_number": data.get("invoice_number"),
        "invoice_date": data.get("invoice_date"),
        "total_amount": amount,
        "document_type": doc_type,
        "confidence_score": data.get("confidence_score", 0),
        "route": "",
    }

    result = {
        "filename": filename,
        "timestamp": timestamp,
        "amount": amount,
        "vendor": vendor,
        "route": "",
        "route_details": "",
        "processing_status": status,
    }

    # ---- Routing Decision ----

    if status == "failed" or doc_type == "unknown":
        # → Human review queue
        result["route"] = "Human Review"
        result["route_details"] = "Sent to human review queue for manual inspection"
        csv_row["route"] = "Human Review"
        _append_to_human_review(filename, data)
        log_routing(filename, "Human Review", amount, "queued")

    elif amount > 50000:
        # → High Value route
        result["route"] = "High Value"
        slack_msg = _simulate_slack_notification(filename, amount, vendor)
        result["route_details"] = f"High-value invoice — Slack notification sent"
        result["slack_notification"] = slack_msg
        csv_row["route"] = "High Value"
        _append_to_csv(csv_row)
        log_routing(filename, "High Value", amount, "notified")

    else:
        # → Standard CSV route
        result["route"] = "Standard"
        result["route_details"] = "Saved to invoices.csv"
        csv_row["route"] = "Standard"
        _append_to_csv(csv_row)
        log_routing(filename, "Standard", amount, "saved")

    return result
