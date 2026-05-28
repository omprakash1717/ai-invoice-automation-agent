# 🧾 AI Invoice Automation Agent

An intelligent, production-ready invoice processing system that uses **Google Gemini AI** to automatically extract, classify, and route invoices from PDF and image uploads. 

This project demonstrates a complete document processing pipeline, showcasing skills in **backend development (Flask)**, **AI integration (Google Gemini Vision)**, **OCR processing**, and **clean architecture**.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-green?logo=flask)
![Gemini](https://img.shields.io/badge/Google_Gemini-1.5_Flash-orange?logo=google)

---

## ✨ Core Features & Technical Highlights

- **Multi-format Support**: Robust handling of PDFs, JPGs, and PNGs with fallback mechanisms (OCR to Gemini Vision).
- **Intelligent Data Extraction**: Uses structured prompting with Gemini AI to accurately extract vendors, amounts, dates, and line items.
- **Document Classification**: Automatically classifies documents as `standard_invoice`, `credit_note`, or `unknown`.
- **Conditional Routing**: 
  - **High-Value (>₹50,000)** → Triggers a simulated Slack alert.
  - **Standard** → Logs to CSV and standard processing.
  - **Unknown** → Routed for human review.
- **Concurrent Batch Processing**: Efficiently handles multiple file uploads using `concurrent.futures.ThreadPoolExecutor` for parallel AI processing.
- **Robust Error Handling & Quota Management**: Gracefully handles API rate limits, transient failures, and bad file formats.
- **Premium Glassmorphism Dashboard**: A modern, responsive UI with drag-and-drop file upload, built without heavy frontend frameworks.
- **Centralized Logging System**: Detailed processing, routing, error, and API logs for audit trails.

---

## 🛠️ Technology Stack

- **Backend Architecture:** Python 3.8+, Flask, Threading
- **AI & ML Integration:** Google Gemini 1.5 Flash API
- **Document Processing:** `pdfplumber` (PDF text extraction), `pytesseract` + Pillow (Image OCR)
- **Data Management:** Pandas, CSV, File I/O
- **Frontend Design:** HTML5, Vanilla CSS3 (Glassmorphism theme), JavaScript (Fetch API, DOM manipulation)

---

## 🚀 Setup & Installation Guide

Follow these steps to run the project locally for evaluation.

### Prerequisites

1. **Python 3.8+** installed on your system.
2. **Google Gemini API Key** — [Get your free API key here](https://aistudio.google.com/apikey).
3. *(Optional for images)* **Tesseract OCR** — [Download and Install Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/omprakash1717/ai-invoice-automation-agent.git
   cd ai-invoice-automation-agent
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   - Create a `.env` file in the root directory (you can copy from a sample if available, or just create it).
   - Add your Gemini API key:
     ```env
     GEMINI_API_KEY=your_actual_api_key_here
     ```

5. **Run the Application:**
   ```bash
   python app.py
   ```
   The server will start on `http://localhost:5000`.

---

## 📁 System Architecture & Directory Structure

```text
ai-invoice-automation-agent/
├── app.py              # Main Flask application & concurrent processing logic
├── config.py           # Configuration management and environment variables
├── extractor.py        # Gemini AI prompt engineering and data extraction
├── parser.py           # Document parsing (PDF text extraction & OCR)
├── router.py           # Business logic for document classification and routing
├── logger.py           # Custom logging utility (processing, errors, webhook events)
├── utils.py            # Helper functions for IDs, timestamps, and validation
├── requirements.txt    # Project dependencies
├── templates/          # Frontend HTML dashboard
│   └── index.html      
├── static/             # Frontend assets (CSS, JS)
├── uploads/            # Temporary storage for uploaded files
├── logs/               # Application and processing logs
├── csv/                # Structured output exports
└── sample_output/      # Extracted JSON outputs
```

---

## 🔍 Evaluation Guide

For interview evaluation, I recommend testing the following flows:

1. **Upload standard invoices**: Upload a clear PDF invoice. Check the extracted JSON and verify it successfully routes to CSV.
2. **Upload high-value invoices**: Upload an invoice with a total > 50,000. Verify the "High Value" routing and simulated Slack alert.
3. **Upload an image invoice**: Upload a JPG/PNG. The system will attempt OCR and fall back to Gemini Vision if text extraction is weak.
4. **Batch Processing**: Select 5+ files at once to see the `ThreadPoolExecutor` handle them concurrently.
5. **View Logs**: Check the logs section in the UI to see detailed step-by-step processing trails.

---

## 🔮 Future Enhancements (Post-MVP)

If I were to scale this for a production environment, I would add:
- **Relational Database (PostgreSQL)**: To replace in-memory storage for processed results.
- **Asynchronous Task Queue (Celery/Redis)**: For true background processing and scalability.
- **Actual Webhooks**: Implementing real Slack/Microsoft Teams notifications instead of simulated logs.
- **Dockerization**: A `Dockerfile` and `docker-compose.yml` for seamless deployment.

---

*Developed by Omprakash as part of an interview assignment.*
