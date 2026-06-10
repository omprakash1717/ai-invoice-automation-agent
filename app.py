"""
app.py — Flask Application & API Routes
=========================================
Main entry point for the AI Invoice Automation application.
Defines all API endpoints and serves the frontend dashboard.
"""

import os
import json
import time
from datetime import datetime

from flask import (
    Flask, request, jsonify, render_template,
    send_file, send_from_directory
)
from werkzeug.utils import secure_filename
import pandas as pd

from config import (
    UPLOAD_FOLDER, CSV_FOLDER, SAMPLE_OUTPUT_FOLDER,
    MAX_CONTENT_LENGTH, SECRET_KEY, FLASK_DEBUG, ALLOWED_EXTENSIONS, BASE_DIR
)
from utils import validate_file, generate_id, format_timestamp, get_file_extension
from extractor import extract_invoice_data
from router import route_invoice
from logger import log_processing, log_error, read_logs

# ---------------------------------------------------------------------------
# Flask App Setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# In-memory store for processed results (persists during server lifetime)
# In production you'd use a database — this is fine for a demo.
processed_results = {}

# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    """
    POST /upload
    Accept one or more invoice files, run the full pipeline:
      1. Validate & save file
      2. Extract text (OCR / pdfplumber)
      3. Send to Gemini for structured extraction
      4. Apply routing logic
      5. Return results
    """
    # Check that files were included in the request
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files selected"}), 400

    results = []
    
    # Save all uploaded files to build a mapping and isolate JSON files
    uploaded_files_map = {}
    json_files = []
    
    for file in files:
        filename = secure_filename(file.filename)
        if not validate_file(filename):
            results.append({"filename": filename, "status": "failed", "error": "Unsupported file type."})
            continue

        proc_id = generate_id()
        filepath = os.path.join(UPLOAD_FOLDER, f"{proc_id}_{filename}")
        file.save(filepath)
        uploaded_files_map[filename] = filepath
        
        if get_file_extension(filename) == "json":
            json_files.append((filename, filepath))

    files_to_process = []
    referenced_files = set()
    
    # Process webhook JSON payloads
    for filename, filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            log_processing(filename, "webhook", f"Parsing webhook payload with {len(payload.get('events', []))} events")
            for event in payload.get("events", []):
                att = event.get("attachment", {})
                att_filename = att.get("filename", "")
                local_path = att.get("local_path", "")
                
                # Robust resolution logic
                resolved_path = None
                
                # Check 1: Was it uploaded in the same batch?
                if att_filename in uploaded_files_map:
                    resolved_path = uploaded_files_map[att_filename]
                    referenced_files.add(att_filename)
                
                # Check 2: Check local_path specified in JSON relative to BASE_DIR
                elif local_path:
                    abs_path = os.path.normpath(os.path.join(BASE_DIR, local_path))
                    if os.path.exists(abs_path):
                        resolved_path = abs_path
                
                # Check 3: Check inside sample_invoices/ using attachment filename
                if not resolved_path and att_filename:
                    sample_path = os.path.join(BASE_DIR, "sample_invoices", att_filename)
                    if os.path.exists(sample_path):
                        resolved_path = sample_path
                
                # Check 4: Check inside UPLOAD_FOLDER directly
                if not resolved_path and att_filename:
                    upload_path = os.path.join(UPLOAD_FOLDER, att_filename)
                    if os.path.exists(upload_path):
                        resolved_path = upload_path

                if resolved_path:
                    files_to_process.append((att_filename or os.path.basename(resolved_path), resolved_path))
                else:
                    err_filename = att_filename or (os.path.basename(local_path) if local_path else "unknown")
                    results.append({"filename": err_filename, "status": "failed", "error": "File not found locally."})
                    log_error(filename, "webhook", f"File not found for event: {event.get('event_id', 'unknown')}")
        except Exception as e:
            log_error(filename, "webhook_parse", str(e))
            results.append({"filename": filename, "status": "failed", "error": "Invalid webhook JSON payload."})

    # Process standard files uploaded that were not part of webhook referenced files
    for filename, filepath in uploaded_files_map.items():
        if get_file_extension(filename) != "json" and filename not in referenced_files:
            files_to_process.append((filename, filepath))

    # 2. Run the AI pipeline on all gathered files concurrently
    import concurrent.futures

    def process_file_pipeline(filename, filepath):
        proc_id = generate_id()

        # --- Step 1: Gemini AI extraction ---
        log_processing(filename, "processing", "Sending file to Gemini AI for native extraction")
        invoice_data = extract_invoice_data(filename, filepath)

        # Check if we hit a fatal API limit/quota error
        is_fatal_quota = False
        if invoice_data.get("status") == "failed" and invoice_data.get("error"):
            err_msg = invoice_data["error"].lower()
            if any(k in err_msg for k in ["quota", "limit", "resource_exhausted", "429"]):
                is_fatal_quota = True

        # --- Step 3: Routing ---
        log_processing(filename, "processing", "Applying routing logic")
        routing_result = route_invoice(invoice_data, filename)

        # --- Build final result ---
        result = {
            "id": proc_id,
            "filename": filename,
            "status": invoice_data.get("status", "failed"),
            "invoice_data": {
                "document_type": invoice_data.get("document_type"),
                "vendor_name": invoice_data.get("vendor_name"),
                "invoice_number": invoice_data.get("invoice_number"),
                "invoice_date": invoice_data.get("invoice_date"),
                "total_amount": invoice_data.get("total_amount"),
                "line_items": invoice_data.get("line_items", []),
                "confidence_score": invoice_data.get("confidence_score", 0),
            },
            "routing": routing_result,
            "extracted_text_preview": "[Native Gemini Extraction]",
            "processed_at": format_timestamp(),
        }

        if invoice_data.get("error"):
            result["error"] = invoice_data["error"]
            
        return result, is_fatal_quota

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_file = {
            executor.submit(process_file_pipeline, filename, filepath): (filename, filepath)
            for filename, filepath in files_to_process
        }

        quota_exhausted = False

        for future in concurrent.futures.as_completed(future_to_file):
            filename, filepath = future_to_file[future]
            try:
                if quota_exhausted:
                    # Append a skipped result so the frontend knows this file wasn't processed
                    skipped_id = generate_id()
                    skipped_result = {
                        "id": skipped_id,
                        "filename": filename,
                        "status": "failed",
                        "error": "Skipped due to API quota exhaustion",
                        "invoice_data": {
                            "document_type": "unknown", "vendor_name": None, "invoice_number": None,
                            "invoice_date": None, "total_amount": 0, "line_items": [], "confidence_score": 0,
                        },
                        "routing": {
                            "filename": filename, "timestamp": format_timestamp(), "amount": 0,
                            "vendor": "Unknown", "route": "Skipped",
                            "route_details": "Processing stopped due to API limits", "processing_status": "failed"
                        },
                        "extracted_text_preview": "[Skipped]",
                        "processed_at": format_timestamp(),
                    }
                    processed_results[skipped_id] = skipped_result
                    
                    try:
                        with open(os.path.join(SAMPLE_OUTPUT_FOLDER, f"{skipped_id}.json"), "w", encoding="utf-8") as f:
                            json.dump(skipped_result, f, indent=2, default=str)
                    except Exception:
                        pass
                        
                    results.append(skipped_result)
                    continue

                result, is_fatal_quota = future.result()
                proc_id = result["id"]

                # Save to in-memory store
                processed_results[proc_id] = result

                # Save JSON to sample_output for download
                output_path = os.path.join(SAMPLE_OUTPUT_FOLDER, f"{proc_id}.json")
                try:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, default=str)
                except Exception:
                    pass

                log_processing(filename, "completed", f"Processing complete — route: {result.get('routing', {}).get('route')}")
                results.append(result)

                if is_fatal_quota:
                    quota_exhausted = True
                    log_error(filename, "batch_processing", f"Stopping batch processing due to API quota exhaustion")
                    # Cancel remaining futures to avoid unnecessary API calls
                    for f in future_to_file:
                        f.cancel()

            except Exception as exc:
                log_error(filename, "batch_processing", f"File generated an exception: {exc}")
                failed_proc_id = generate_id()
                failed_result = {
                    "id": failed_proc_id,
                    "filename": filename,
                    "status": "failed",
                    "error": f"Internal error during processing: {str(exc)}",
                    "invoice_data": {
                        "document_type": "unknown", "vendor_name": None, "invoice_number": None,
                        "invoice_date": None, "total_amount": 0, "line_items": [], "confidence_score": 0,
                    },
                    "routing": {
                        "filename": filename, "timestamp": format_timestamp(), "amount": 0,
                        "vendor": "Unknown", "route": "Human Review",
                        "route_details": "Failed due to internal error", "processing_status": "failed"
                    },
                    "extracted_text_preview": "[Failed]",
                    "processed_at": format_timestamp(),
                }
                processed_results[failed_proc_id] = failed_result
                
                try:
                    with open(os.path.join(SAMPLE_OUTPUT_FOLDER, f"{failed_proc_id}.json"), "w", encoding="utf-8") as f:
                        json.dump(failed_result, f, indent=2, default=str)
                except Exception:
                    pass
                    
                results.append(failed_result)

    # Note: we don't append placeholder "Skipped" results for cancelled futures here,
    # as parallel execution makes order unpredictable and returning only processed/failed ones is cleaner.

    return jsonify({
        "message": f"Processed {len(results)} file(s)",
        "results": results,
    })


@app.route("/logs", methods=["GET"])
def get_logs():
    """
    GET /logs?type=processing&limit=50
    Return processing logs.  Supported types:
      processing, routing, failed, ocr, api
    """
    log_type = request.args.get("type", "processing")
    limit = request.args.get("limit", 100, type=int)

    valid_types = {"processing", "routing", "failed", "ocr", "api"}
    if log_type not in valid_types:
        return jsonify({"error": f"Invalid log type. Valid: {', '.join(valid_types)}"}), 400

    logs = read_logs(log_type, limit)
    return jsonify({"type": log_type, "count": len(logs), "logs": logs})


@app.route("/results", methods=["GET"])
def get_results():
    """
    GET /results
    Return all processed invoice results.
    """
    results_list = list(processed_results.values())
    # Sort by processed_at descending
    results_list.sort(key=lambda r: r.get("processed_at", ""), reverse=True)
    return jsonify({
        "count": len(results_list),
        "results": results_list,
    })


@app.route("/download/json/<proc_id>", methods=["GET"])
def download_json(proc_id):
    """
    GET /download/json/<id>
    Download the extracted JSON for a specific processing ID.
    """
    output_path = os.path.join(SAMPLE_OUTPUT_FOLDER, f"{proc_id}.json")
    if not os.path.exists(output_path):
        return jsonify({"error": "Result not found"}), 404

    return send_file(
        output_path,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"invoice_{proc_id}.json",
    )


@app.route("/export/csv", methods=["GET"])
def export_csv():
    """
    GET /export/csv
    Export the invoices.csv file.
    """
    csv_path = os.path.join(CSV_FOLDER, "invoices.csv")

    if not os.path.exists(csv_path):
        return jsonify({"error": "No CSV data available yet. Process some invoices first."}), 404

    return send_file(
        csv_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name="invoices_export.csv",
    )


@app.route("/stats", methods=["GET"])
def get_stats():
    """
    GET /stats
    Return dashboard statistics.
    """
    total = len(processed_results)
    success = sum(1 for r in processed_results.values() if r.get("status") == "success")
    partial = sum(1 for r in processed_results.values() if r.get("status") == "partial")
    failed = sum(1 for r in processed_results.values() if r.get("status") == "failed")

    high_value = sum(
        1 for r in processed_results.values()
        if r.get("routing", {}).get("route") == "High Value"
    )

    total_amount = sum(
        r.get("invoice_data", {}).get("total_amount", 0)
        for r in processed_results.values()
        if r.get("status") in ("success", "partial")
    )

    return jsonify({
        "total_processed": total,
        "success": success,
        "partial": partial,
        "failed": failed,
        "high_value": high_value,
        "total_amount": round(total_amount, 2),
    })


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  AI Invoice Automation System")
    print("  Running at: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=FLASK_DEBUG, host="0.0.0.0", port=5000)
