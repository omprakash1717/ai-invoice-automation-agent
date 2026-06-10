/**
 * app.js — Frontend Logic for InvoiceAI Dashboard
 * ==================================================
 * Handles: drag-drop upload, fetch API calls, dynamic rendering,
 * toast notifications, JSON viewer, CSV export, stats updates.
 */

// ── State ────────────────────────────────────────────────────────────
let selectedFiles = [];
let currentLogType = "processing";
let currentModalData = null;

// ── DOM References ───────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const uploadZone       = $("#uploadZone");
const fileInput        = $("#fileInput");
const filePreviewList  = $("#filePreviewList");
const uploadActions    = $("#uploadActions");
const processBtn       = $("#processBtn");
const clearFilesBtn    = $("#clearFilesBtn");
const progressContainer= $("#uploadProgressContainer");
const progressFill     = $("#progressFill");
const progressText     = $("#progressText");
const resultsContainer = $("#resultsContainer");
const emptyState       = $("#emptyState");
const logsTableBody    = $("#logsTableBody");
const toastContainer   = $("#toastContainer");
const jsonModal        = $("#jsonModal");
const jsonViewer       = $("#jsonViewer");
const modalTitle       = $("#modalTitle");
const exportCsvBtn     = $("#exportCsvBtn");
const refreshLogsBtn   = $("#refreshLogsBtn");

// ── Initialisation ───────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupUploadZone();
    setupLogTabs();
    setupModalEvents();
    setupExportBtn();
    setupRefreshLogs();
    refreshStats();
    fetchResults();
    fetchLogs("processing");
});

// ══════════════════════════════════════════════════════════════════════
// UPLOAD HANDLING
// ══════════════════════════════════════════════════════════════════════

function setupUploadZone() {
    // Click to browse
    uploadZone.addEventListener("click", (e) => {
        if (e.target.closest(".upload-progress-container")) return;
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        addFiles(Array.from(e.target.files));
        fileInput.value = "";
    });

    // Drag & drop
    uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadZone.classList.add("drag-over");
    });
    uploadZone.addEventListener("dragleave", () => {
        uploadZone.classList.remove("drag-over");
    });
    uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadZone.classList.remove("drag-over");
        addFiles(Array.from(e.dataTransfer.files));
    });

    // Process & clear buttons
    processBtn.addEventListener("click", uploadFiles);
    clearFilesBtn.addEventListener("click", clearFiles);
}

function addFiles(files) {
    const allowed = ["pdf", "jpg", "jpeg", "png", "json"];
    files.forEach((f) => {
        const ext = f.name.split(".").pop().toLowerCase();
        if (allowed.includes(ext)) {
            selectedFiles.push(f);
        } else {
            showToast(`Unsupported file: ${f.name}`, "error");
        }
    });
    renderFilePreviews();
}

function renderFilePreviews() {
    filePreviewList.innerHTML = "";
    if (selectedFiles.length === 0) {
        uploadActions.style.display = "none";
        return;
    }
    uploadActions.style.display = "flex";

    selectedFiles.forEach((f, i) => {
        const icon = f.name.toLowerCase().endsWith(".pdf") ? "📄" : "🖼️";
        const size = (f.size / 1024).toFixed(1) + " KB";
        const el = document.createElement("div");
        el.className = "file-preview-item";
        el.innerHTML = `
            <span class="file-icon">${icon}</span>
            <span class="file-name">${f.name}</span>
            <span class="file-size">${size}</span>
            <span class="file-remove" data-index="${i}">&times;</span>`;
        filePreviewList.appendChild(el);
    });

    // Remove button handlers
    $$(".file-remove").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.index);
            selectedFiles.splice(idx, 1);
            renderFilePreviews();
        });
    });
}

function clearFiles() {
    selectedFiles = [];
    renderFilePreviews();
}

// ── Upload to server ─────────────────────────────────────────────────

async function uploadFiles() {
    if (selectedFiles.length === 0) {
        showToast("Please select files first", "error");
        return;
    }

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append("files", f));

    // Show progress
    progressContainer.style.display = "block";
    progressFill.style.width = "0%";
    progressText.textContent = "Uploading & processing...";
    processBtn.disabled = true;
    processBtn.innerHTML = '<span class="spinner"></span> Processing...';

    // Simulate progress
    let progress = 0;
    const progressTimer = setInterval(() => {
        progress = Math.min(progress + Math.random() * 15, 90);
        progressFill.style.width = progress + "%";
    }, 400);

    try {
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();

        clearInterval(progressTimer);
        progressFill.style.width = "100%";
        progressText.textContent = "Complete!";

        if (res.ok) {
            showToast(`Processed ${data.results.length} file(s) successfully!`, "success");
            renderResults(data.results);
            refreshStats();
            fetchLogs(currentLogType);
            clearFiles();
        } else {
            showToast(data.error || "Upload failed", "error");
        }
    } catch (err) {
        clearInterval(progressTimer);
        showToast("Network error: " + err.message, "error");
    } finally {
        setTimeout(() => {
            progressContainer.style.display = "none";
            processBtn.disabled = false;
            processBtn.innerHTML = "🚀 Process Invoices";
        }, 1500);
    }
}

// ══════════════════════════════════════════════════════════════════════
// RESULTS RENDERING
// ══════════════════════════════════════════════════════════════════════

function renderResults(results) {
    if (emptyState) emptyState.style.display = "none";

    results.forEach((r) => {
        const card = document.createElement("div");
        card.className = "result-card";
        card.innerHTML = buildResultCard(r);
        resultsContainer.prepend(card);
    });

    // Attach event listeners for new cards
    attachResultCardEvents();
}

function buildResultCard(r) {
    const inv = r.invoice_data || {};
    const routing = r.routing || {};
    const status = r.status || "failed";

    // Badge classes
    const statusBadge = status === "success" ? "badge-success"
                      : status === "partial" ? "badge-partial" : "badge-failed";
    const routeBadge = routing.route === "High Value" ? "badge-high" : "badge-route";

    // Confidence bar
    const conf = (inv.confidence_score || 0);
    const confPct = Math.round(conf * 100);
    const confClass = conf >= 0.7 ? "confidence-high" : conf >= 0.4 ? "confidence-mid" : "confidence-low";

    // Line items
    let lineItemsHTML = "";
    if (inv.line_items && inv.line_items.length > 0) {
        lineItemsHTML = `
        <div class="line-items-section">
            <div class="line-items-title">Line Items</div>
            <table class="line-items-table">
                <thead><tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr></thead>
                <tbody>${inv.line_items.map((li) => `
                    <tr>
                        <td>${li.description || "—"}</td>
                        <td>${li.quantity ?? "—"}</td>
                        <td>${li.unit_price != null ? "₹" + Number(li.unit_price).toLocaleString() : "—"}</td>
                        <td>${li.amount != null ? "₹" + Number(li.amount).toLocaleString() : "—"}</td>
                    </tr>`).join("")}
                </tbody>
            </table>
        </div>`;
    }

    return `
    <div class="result-header">
        <div class="result-filename">📄 ${r.filename}</div>
        <div class="result-badges">
            <span class="badge ${statusBadge}">${status}</span>
            ${routing.route ? `<span class="badge ${routeBadge}">${routing.route}</span>` : ""}
            <span class="badge badge-route">${inv.document_type || "unknown"}</span>
        </div>
    </div>
    <div class="result-body">
        <div class="result-field">
            <span class="result-label">Vendor</span>
            <span class="result-value">${inv.vendor_name || "—"}</span>
        </div>
        <div class="result-field">
            <span class="result-label">Invoice #</span>
            <span class="result-value">${inv.invoice_number || "—"}</span>
        </div>
        <div class="result-field">
            <span class="result-label">Date</span>
            <span class="result-value">${inv.invoice_date || "—"}</span>
        </div>
        <div class="result-field">
            <span class="result-label">Total Amount</span>
            <span class="result-value" style="font-size:18px;font-weight:700;color:var(--success)">
                ₹${inv.total_amount != null ? Number(inv.total_amount).toLocaleString("en-IN", {minimumFractionDigits:2}) : "0.00"}
            </span>
        </div>
        <div class="result-field">
            <span class="result-label">Confidence</span>
            <span class="result-value">${confPct}%</span>
            <div class="confidence-bar"><div class="confidence-fill ${confClass}" style="width:${confPct}%"></div></div>
        </div>
        <div class="result-field">
            <span class="result-label">Routing</span>
            <span class="result-value">${routing.route_details || "—"}</span>
        </div>
        ${lineItemsHTML}
        ${r.error ? `<div class="result-field" style="grid-column:1/-1"><span class="result-label" style="color:var(--danger)">Error</span><span class="result-value" style="color:var(--danger)">${r.error}</span></div>` : ""}
    </div>
    <div class="result-footer">
        <button class="btn btn-outline btn-sm view-json-btn" data-id="${r.id}">🔍 View JSON</button>
        <button class="btn btn-outline btn-sm download-json-btn" data-id="${r.id}">📥 Download JSON</button>
    </div>`;
}

function attachResultCardEvents() {
    $$(".view-json-btn").forEach((btn) => {
        btn.onclick = () => viewJSON(btn.dataset.id);
    });
    $$(".download-json-btn").forEach((btn) => {
        btn.onclick = () => downloadJSON(btn.dataset.id);
    });
}

// ── Fetch existing results on load ───────────────────────────────────

async function fetchResults() {
    try {
        const res = await fetch("/results");
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            renderResults(data.results);
        }
    } catch (_) { /* silent */ }
}

// ══════════════════════════════════════════════════════════════════════
// STATS
// ══════════════════════════════════════════════════════════════════════

async function refreshStats() {
    try {
        const res = await fetch("/stats");
        const s = await res.json();
        animateValue("statTotalValue", s.total_processed);
        animateValue("statSuccessValue", s.success);
        animateValue("statFailedValue", s.failed);
        animateValue("statHighValueValue", s.high_value);
        $("#statAmountValue").textContent = "₹" + Number(s.total_amount).toLocaleString("en-IN", {minimumFractionDigits:2});
    } catch (_) { /* silent */ }
}

function animateValue(elemId, target) {
    const el = document.getElementById(elemId);
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    if (start === target) return;
    const duration = 600;
    const startTime = performance.now();
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        el.textContent = Math.round(start + (target - start) * progress);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ══════════════════════════════════════════════════════════════════════
// LOGS
// ══════════════════════════════════════════════════════════════════════

function setupLogTabs() {
    $$(".log-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            $$(".log-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            currentLogType = tab.dataset.type;
            fetchLogs(currentLogType);
        });
    });
}

function setupRefreshLogs() {
    refreshLogsBtn.addEventListener("click", () => fetchLogs(currentLogType));
}

async function fetchLogs(type) {
    try {
        const res = await fetch(`/logs?type=${type}&limit=50`);
        const data = await res.json();
        renderLogs(data.logs || []);
    } catch (_) {
        logsTableBody.innerHTML = `<tr class="log-empty"><td colspan="4">Failed to load logs.</td></tr>`;
    }
}

function renderLogs(logs) {
    if (logs.length === 0) {
        logsTableBody.innerHTML = `<tr class="log-empty"><td colspan="4">No logs available.</td></tr>`;
        return;
    }
    logsTableBody.innerHTML = logs.map((l) => {
        const ts = l.timestamp ? new Date(l.timestamp).toLocaleString() : "—";
        const file = l.filename || "—";
        const status = l.status || l.type || "—";
        const detail = l.message || l.error || l.method || l.route || "—";
        return `<tr><td>${ts}</td><td>${file}</td><td>${status}</td><td>${detail}</td></tr>`;
    }).join("");
}

// ══════════════════════════════════════════════════════════════════════
// JSON MODAL
// ══════════════════════════════════════════════════════════════════════

function setupModalEvents() {
    $("#modalClose").addEventListener("click", closeModal);
    jsonModal.addEventListener("click", (e) => { if (e.target === jsonModal) closeModal(); });
    $("#modalCopyBtn").addEventListener("click", () => {
        if (currentModalData) {
            navigator.clipboard.writeText(JSON.stringify(currentModalData, null, 2));
            showToast("JSON copied to clipboard", "info");
        }
    });
    $("#modalDownloadBtn").addEventListener("click", () => {
        if (currentModalData && currentModalData.id) downloadJSON(currentModalData.id);
    });
}

async function viewJSON(id) {
    try {
        const res = await fetch(`/download/json/${id}`);
        const data = await res.json();
        currentModalData = data;
        modalTitle.textContent = `Invoice: ${data.filename || id}`;
        jsonViewer.textContent = JSON.stringify(data, null, 2);
        jsonModal.style.display = "flex";
    } catch (err) {
        showToast("Could not load JSON", "error");
    }
}

function closeModal() {
    jsonModal.style.display = "none";
    currentModalData = null;
}

// ══════════════════════════════════════════════════════════════════════
// DOWNLOADS & EXPORTS
// ══════════════════════════════════════════════════════════════════════

function downloadJSON(id) {
    window.open(`/download/json/${id}`, "_blank");
}

function setupExportBtn() {
    exportCsvBtn.addEventListener("click", async () => {
        try {
            const res = await fetch("/export/csv");
            if (!res.ok) {
                const err = await res.json();
                showToast(err.error || "Export failed", "error");
                return;
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = "invoices_export.csv"; a.click();
            URL.revokeObjectURL(url);
            showToast("CSV exported successfully", "success");
        } catch (err) {
            showToast("Export failed: " + err.message, "error");
        }
    });

    const clearResultsBtn = $("#clearResultsBtn");
    if (clearResultsBtn) {
        clearResultsBtn.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to clear all processed results?")) return;
            try {
                const res = await fetch("/results", { method: "DELETE" });
                if (res.ok) {
                    $("#resultsContainer").innerHTML = `
                        <div class="empty-state" id="emptyState">
                            <div class="empty-icon">📭</div>
                            <h3>No results yet</h3>
                            <p>Upload and process invoices to see extraction results here.</p>
                        </div>
                    `;
                    showToast("Results cleared successfully", "success");
                }
            } catch (err) {
                showToast("Failed to clear results", "error");
            }
        });
    }
}

// ══════════════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ══════════════════════════════════════════════════════════════════════

function showToast(message, type = "info") {
    const icons = { success: "✅", error: "❌", info: "ℹ️" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
