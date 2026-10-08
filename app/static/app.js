/**
 * Bulk Certificate Generator — Dashboard Controller
 */

// Application state
let currentRecipients = [];
let activePollingInterval = null;
let currentJobId = null;

// Initialise on load
document.addEventListener("DOMContentLoaded", () => {
  // Set default issue date to today
  const issueDateInput = document.getElementById("issue-date");
  if (issueDateInput) {
    const today = new Date().toISOString().split("T")[0];
    issueDateInput.value = today;
  }

  setupDropzone();
  fetchRecentJobs();
});

// ── Tab Navigation ──────────────────────────────────────────────────────────

function switchTab(tab) {
  const tabCsv = document.getElementById("tab-csv");
  const tabManual = document.getElementById("tab-manual");
  const panelCsv = document.getElementById("panel-csv");
  const panelManual = document.getElementById("panel-manual");

  if (tab === "csv") {
    tabCsv.classList.add("active");
    tabManual.classList.remove("active");
    panelCsv.classList.add("active");
    panelManual.classList.remove("active");
  } else {
    tabManual.classList.add("active");
    tabCsv.classList.remove("active");
    panelManual.classList.add("active");
    panelCsv.classList.remove("active");
  }
}

// ── Dropzone & File Handling ────────────────────────────────────────────────

function setupDropzone() {
  const dropzone = document.getElementById("csv-dropzone");
  const fileInput = document.getElementById("csv-file-input");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", (e) => {
    // Avoid triggering file picker when clicking action buttons
    if (e.target.closest("button")) return;
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleCsvFile(e.target.files[0]);
    }
  });

  // Drag and drop events
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].name.endsWith(".csv")) {
      handleCsvFile(files[0]);
    } else {
      showError("Please upload a valid .csv file.");
    }
  });
}

function handleCsvFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    parseCsvText(text, file.name);
  };
  reader.onerror = () => {
    showError("Failed to read the selected CSV file.");
  };
  reader.readAsText(file);
}

// ── CSV Parsing Logic ───────────────────────────────────────────────────────

function parseCsvText(csvText, filename = "") {
  clearError();
  const lines = csvText.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);

  if (lines.length === 0) {
    showError("The CSV file is empty.");
    return;
  }

  const recipients = [];
  let headerIndex = -1;
  let nameCol = 0;
  let emailCol = 1;

  // Check if first row is header
  const firstRowCols = parseCsvLine(lines[0]).map((c) => c.toLowerCase().trim());
  const hasName = firstRowCols.some((c) => c.includes("name"));
  const hasEmail = firstRowCols.some((c) => c.includes("email") || c.includes("mail"));

  if (hasName && hasEmail) {
    headerIndex = 0;
    nameCol = firstRowCols.findIndex((c) => c.includes("name"));
    emailCol = firstRowCols.findIndex((c) => c.includes("email") || c.includes("mail"));
  }

  const startLine = headerIndex >= 0 ? 1 : 0;

  for (let i = startLine; i < lines.length; i++) {
    const cols = parseCsvLine(lines[i]);
    if (cols.length < 2) continue;

    const name = (cols[nameCol] || "").trim();
    const email = (cols[emailCol] || "").trim();

    if (name && email) {
      recipients.push({ name, email });
    }
  }

  if (recipients.length === 0) {
    showError("No valid recipients found in CSV. Please verify column headers ('name', 'email').");
    return;
  }

  setRecipients(recipients);
  showToast(`Parsed ${recipients.length} recipients from ${filename || "CSV"}`);
}

function parseCsvLine(text) {
  const result = [];
  let cur = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"' || char === "'") {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      result.push(cur.trim());
      cur = "";
    } else {
      cur += char;
    }
  }
  result.push(cur.trim());
  return result;
}

// ── Manual Entry Parsing ────────────────────────────────────────────────────

function parseManualInput() {
  clearError();
  const text = document.getElementById("manual-text").value.trim();
  if (!text) {
    currentRecipients = [];
    updatePreviewTable();
    return;
  }

  const lines = text.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);
  const recipients = [];

  for (const line of lines) {
    const parts = line.split(",").map((p) => p.trim());
    if (parts.length >= 2) {
      recipients.push({ name: parts[0], email: parts[1] });
    }
  }

  setRecipients(recipients);
}

// ── Recipients State & Preview Table ────────────────────────────────────────

function setRecipients(recipients) {
  currentRecipients = recipients;
  updatePreviewTable();
}

function clearRecipients() {
  currentRecipients = [];
  const manualText = document.getElementById("manual-text");
  if (manualText) manualText.value = "";
  const fileInput = document.getElementById("csv-file-input");
  if (fileInput) fileInput.value = "";
  updatePreviewTable();
  clearError();
}

function updatePreviewTable() {
  const previewSection = document.getElementById("recipients-preview");
  const countBadge = document.getElementById("recipients-count-badge");
  const tbody = document.getElementById("preview-tbody");
  const submitBtn = document.getElementById("submit-job-btn");
  const btnText = document.getElementById("btn-text");

  if (!previewSection || !tbody) return;

  if (currentRecipients.length === 0) {
    previewSection.style.display = "none";
    if (btnText) btnText.textContent = "Generate Certificates";
    return;
  }

  previewSection.style.display = "block";
  countBadge.textContent = `${currentRecipients.length} recipients`;
  if (btnText) btnText.textContent = `Generate ${currentRecipients.length} Certificates`;

  // Render first 10 rows
  const displayLimit = 10;
  const rowsHtml = currentRecipients.slice(0, displayLimit).map((r, idx) => {
    const isValidEmail = validateEmail(r.email);
    const statusPill = isValidEmail
      ? `<span style="color:#34d399; font-weight:600;">Valid</span>`
      : `<span style="color:#f87171; font-weight:600;">Invalid Email</span>`;

    return `
      <tr>
        <td style="color:#9ca3af;">${idx + 1}</td>
        <td><strong>${escapeHtml(r.name)}</strong></td>
        <td><code>${escapeHtml(r.email)}</code></td>
        <td>${statusPill}</td>
      </tr>
    `;
  }).join("");

  const extraCount = currentRecipients.length - displayLimit;
  const extraRow = extraCount > 0
    ? `<tr><td colspan="4" style="text-align:center; color:#9ca3af; font-style:italic;">+ ${extraCount} more recipients</td></tr>`
    : "";

  tbody.innerHTML = rowsHtml + extraRow;
}

// ── Sample Data Generators ──────────────────────────────────────────────────

function downloadSampleCsv() {
  const csvContent = "name,email\n" +
    "Lanson Bardeskar,lanson.bardeskar@example.com\n" +
    "Saurav Swami,saurav.swami@example.com\n" +
    "Kanif Kumbhar,kanif.kumbhar@example.com\n";

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", "recipients_template.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast("Sample template downloaded!");
}

function loadSampleCsvData() {
  const sampleData = [
    { name: "Lanson Bardeskar", email: "lanson.bardeskar@example.com" },
    { name: "Saurav Swami", email: "saurav.swami@example.com" },
    { name: "Kanif Kumbhar", email: "kanif.kumbhar@example.com" },
  ];
  setRecipients(sampleData);
  showToast("Loaded 3 sample recipients!");
}

function loadSampleManualData() {
  const sample = "Lanson Bardeskar, lanson.bardeskar@example.com\n" +
    "Saurav Swami, saurav.swami@example.com\n" +
    "Kanif Kumbhar, kanif.kumbhar@example.com";
  document.getElementById("manual-text").value = sample;
  parseManualInput();
  showToast("Filled sample recipients!");
}

// ── Job Submission & API Calls ──────────────────────────────────────────────

async function submitGenerationJob() {
  clearError();

  const courseName = document.getElementById("course-name").value.trim();
  const issueDate = document.getElementById("issue-date").value.trim();

  if (!courseName) {
    showError("Please enter a course or event name.");
    return;
  }

  if (!issueDate) {
    showError("Please select a valid issue date.");
    return;
  }

  if (currentRecipients.length === 0) {
    showError("Please provide at least one recipient (via CSV upload or manual entry).");
    return;
  }

  // Validate duplicate emails
  const emails = currentRecipients.map((r) => r.email.toLowerCase());
  const seen = new Set();
  const duplicates = [];
  for (const email of emails) {
    if (seen.has(email)) {
      duplicates.push(email);
    }
    seen.add(email);
  }

  if (duplicates.length > 0) {
    showError(`Duplicate emails found in recipient list: ${duplicates.join(", ")}`);
    return;
  }

  const payload = {
    course_name: courseName,
    issue_date: issueDate,
    recipients: currentRecipients,
  };

  const submitBtn = document.getElementById("submit-job-btn");
  submitBtn.disabled = true;
  submitBtn.style.opacity = "0.7";

  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      let msg = "Failed to create generation job.";
      if (data.detail) {
        if (Array.isArray(data.detail)) {
          msg = data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
        } else {
          msg = data.detail;
        }
      }
      showError(msg);
      return;
    }

    // Job accepted!
    currentJobId = data.job_id;
    showToast(`Job ${data.job_id.substring(0, 8)}... created! Generating in background.`);
    startJobMonitoring(data.job_id, currentRecipients.length);
    fetchRecentJobs();
  } catch (err) {
    showError(`Network error submitting job: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.style.opacity = "1";
  }
}

// ── Live Job Monitoring & Polling ───────────────────────────────────────────

function startJobMonitoring(jobId, totalCount = 0) {
  if (activePollingInterval) {
    clearInterval(activePollingInterval);
  }

  document.getElementById("monitor-empty").style.display = "none";
  document.getElementById("monitor-active").style.display = "block";

  document.getElementById("active-job-id").textContent = jobId;
  updateStatusBadge("pending");
  updateProgressBar(0, totalCount || 1);
  updateStats(totalCount, 0, 0);

  // Poll immediately, then every 700ms
  pollJobStatus(jobId);
  activePollingInterval = setInterval(() => {
    pollJobStatus(jobId);
  }, 700);
}

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) return;

    const job = await res.json();
    updateStatusBadge(job.status);
    updateStats(job.total_count, job.success_count, job.failure_count);

    const processed = job.success_count + job.failure_count;
    updateProgressBar(processed, job.total_count);

    // If job finished, stop polling and load certificates
    if (job.status === "completed" || job.status === "completed_with_errors") {
      clearInterval(activePollingInterval);
      activePollingInterval = null;
      fetchCertificates(jobId);
      fetchRecentJobs();
    }
  } catch (err) {
    console.error("Polling error:", err);
  }
}

function updateStatusBadge(status) {
  const badge = document.getElementById("active-job-status-badge");
  if (!badge) return;

  badge.className = `badge badge-${status}`;
  badge.textContent = status.replace(/_/g, " ");
}

function updateProgressBar(processed, total) {
  const fill = document.getElementById("progress-bar-fill");
  const percentLabel = document.getElementById("progress-percentage");
  const countLabel = document.getElementById("progress-counts");

  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  fill.style.width = `${pct}%`;
  percentLabel.textContent = `${pct}% Completed`;
  countLabel.textContent = `${processed} / ${total}`;
}

function updateStats(total, success, failed) {
  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-success").textContent = success;
  document.getElementById("stat-failed").textContent = failed;
}

// ── Fetch & Render Certificates Table ───────────────────────────────────────

async function fetchCertificates(jobId) {
  const tbody = document.getElementById("certs-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`/api/jobs/${jobId}/certificates`);
    if (!res.ok) return;

    const data = await res.json();
    const certs = data.certificates || [];

    if (certs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#9ca3af;">No certificates found.</td></tr>`;
      return;
    }

    tbody.innerHTML = certs.map((c) => {
      const isSuccess = c.status === "success";
      const statusPill = isSuccess
        ? `<span class="badge badge-completed" style="font-size:0.7rem;">Success</span>`
        : `<span class="badge badge-completed_with_errors" style="font-size:0.7rem;">Failed</span>`;

      const action = isSuccess && c.download_url
        ? `<a href="${c.download_url}" target="_blank" download class="download-link-btn">
             <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
               <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
               <polyline points="7 10 12 15 17 10"></polyline>
               <line x1="12" y1="15" x2="12" y2="3"></line>
             </svg>
             Download PDF
           </a>`
        : `<span style="color:#f87171; font-size:0.75rem;">${escapeHtml(c.error_message || "Error")}</span>`;

      return `
        <tr>
          <td>
            <div class="recipient-cell">
              <span class="recipient-name">${escapeHtml(c.recipient_name)}</span>
              <span class="recipient-email">${escapeHtml(c.recipient_email)}</span>
            </div>
          </td>
          <td>${statusPill}</td>
          <td>${action}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Error fetching certificates:", err);
  }
}

function refreshCertificates() {
  if (currentJobId) {
    fetchCertificates(currentJobId);
    showToast("Refreshed certificates list.");
  }
}

// ── Recent Jobs ─────────────────────────────────────────────────────────────

async function fetchRecentJobs() {
  const container = document.getElementById("recent-jobs-list");
  if (!container) return;

  try {
    const res = await fetch("/api/jobs?limit=5");
    if (!res.ok) return;

    const data = await res.json();
    const jobs = data.jobs || [];

    if (jobs.length === 0) {
      container.innerHTML = `<p class="subtle-loading">No jobs created yet.</p>`;
      return;
    }

    container.innerHTML = jobs.map((j) => {
      return `
        <div class="recent-job-item" onclick="selectRecentJob('${j.id}')">
          <div class="recent-job-info">
            <span class="recent-course">${escapeHtml(j.course_name)}</span>
            <span class="recent-meta">${j.total_count} recipients • ${j.issue_date}</span>
          </div>
          <div>
            <span class="badge badge-${j.status}" style="font-size:0.65rem;">${j.status.replace(/_/g, " ")}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Error fetching recent jobs:", err);
  }
}

function selectRecentJob(jobId) {
  currentJobId = jobId;
  startJobMonitoring(jobId);
  showToast(`Switched to job ${jobId.substring(0, 8)}...`);
}

// ── Helper Utilities ────────────────────────────────────────────────────────

function copyActiveJobId() {
  const id = document.getElementById("active-job-id").textContent;
  if (id && id !== "-") {
    navigator.clipboard.writeText(id).then(() => {
      showToast("Job ID copied to clipboard!");
    });
  }
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showError(msg) {
  const banner = document.getElementById("form-error-banner");
  const msgEl = document.getElementById("form-error-msg");
  if (banner && msgEl) {
    msgEl.textContent = msg;
    banner.style.display = "flex";
  }
}

function clearError() {
  const banner = document.getElementById("form-error-banner");
  if (banner) {
    banner.style.display = "none";
  }
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;

  toast.textContent = msg;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
