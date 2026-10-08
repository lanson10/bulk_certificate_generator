# Bulk Certificate Generator API

A backend API that accepts bulk certificate generation requests, processes them in the background, and provides endpoints to track progress and download generated PDF certificates.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Setup](#setup)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [API Reference](#api-reference)
- [Design Decisions](#design-decisions)
- [Extensibility & Interview Talking Points](#extensibility--interview-talking-points)

---

## Architecture Overview

```
Client
  │
  ├─ POST /api/jobs ──────────────► FastAPI Router
  │                                    │
  │                                    ├─ Pydantic validation
  │                                    ├─ Persist job + certificates (SQLite)
  │                                    └─ Kick off background processing
  │                                           │
  │                                           ▼
  │                                    ThreadPoolExecutor
  │                                    ┌───┬───┬───┐
  │                                    │ T1│ T2│ T3│  (parallel PDF generation)
  │                                    └───┴───┴───┘
  │                                           │
  │                                           ▼
  │                                    Update DB status per certificate
  │
  ├─ GET /api/jobs/{id} ─────────► Poll status & progress counters
  ├─ GET /api/jobs/{id}/certificates ► List individual certificate results
  └─ GET /api/certificates/{id}/download ► Download PDF
```

**Tech Stack:**
- **Framework:** FastAPI (Python 3.10+)
- **Database:** SQLite via SQLAlchemy ORM
- **PDF Generation:** ReportLab
- **Background Processing:** `concurrent.futures.ThreadPoolExecutor`
- **Testing:** pytest + httpx

---

## Setup

### Prerequisites

- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd assignment

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Application

```bash
# Activate the virtual environment (if not already active)
source venv/bin/activate

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API and interactive web interface will be available at:
- **Interactive Web Dashboard:** `http://localhost:8000/` or `http://localhost:8000/dashboard`
- **Swagger UI (Interactive API Docs):** `http://localhost:8000/docs`
- **ReDoc UI:** `http://localhost:8000/redoc`

---

## Interactive Web Dashboard

A web interface is served directly by the backend at `http://localhost:8000/`:
- **CSV Drag & Drop Upload**: Upload any `.csv` file containing `name` and `email` columns (with automatic header detection and validation preview).
- **One-Click Demo Data**: Instantly test certificate generation with pre-populated sample records.
- **Manual Entry Tab**: Paste or edit recipient rows directly.
- **Live Progress Monitor**: Real-time progress bar polling the API until generation completes.
- **Certificate Downloads**: Direct PDF download links and status indicators for each recipient.
- **Batch History**: Click to inspect and retrieve past generation jobs.

---

## Running Tests

```bash
# Activate the virtual environment
source venv/bin/activate

# Run the full test suite
pytest -v

# Run with test coverage report (49 tests, 96% coverage)
pytest --cov=app --cov-report=term-missing -v
```

---

## API Reference

### 1. Create a Generation Job

**`POST /api/jobs`**

Submit a bulk certificate generation request. The API validates the input, creates the job, and processes certificates in the background.

**Request Body:**

```json
{
  "course_name": "Advanced Python Workshop",
  "issue_date": "2026-10-08",
  "recipients": [
    { "name": "Alice Johnson", "email": "alice@example.com" },
    { "name": "Bob Smith", "email": "bob@example.com" },
    { "name": "Charlie Brown", "email": "charlie@example.com" }
  ]
}
```

**Validation Rules:**
| Field | Rules |
|---|---|
| `course_name` | Required, 1–200 characters |
| `issue_date` | Required, valid ISO date (YYYY-MM-DD) |
| `recipients` | Required, 1–1000 entries, no duplicate emails |
| `recipients[].name` | Required, 1–150 characters |
| `recipients[].email` | Required, valid email format |

**Response (`202 Accepted`):**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "total_count": 3,
  "message": "Job created. Certificates are being generated in the background."
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "course_name": "Advanced Python Workshop",
    "issue_date": "2026-10-08",
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com"},
      {"name": "Bob Smith", "email": "bob@example.com"}
    ]
  }'
```

### 2. Create Job from CSV File

**`POST /api/jobs/upload-csv`**

Upload a CSV file directly with `multipart/form-data`. Automatically parses columns matching `name` and `email`.

**Form Fields:**
- `course_name`: string (required)
- `issue_date`: YYYY-MM-DD (required)
- `file`: CSV file attachment (required)

**cURL Example:**

```bash
curl -X POST http://localhost:8000/api/jobs/upload-csv \
  -F "course_name=Advanced Python Workshop" \
  -F "issue_date=2026-10-08" \
  -F "file=@recipients.csv"
```

### 3. Check Job Status

**`GET /api/jobs/{job_id}`**

Poll this endpoint to track progress of a generation job.

**Response (`200 OK`):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "course_name": "Advanced Python Workshop",
  "issue_date": "2026-10-08",
  "status": "completed",
  "total_count": 3,
  "success_count": 3,
  "failure_count": 0,
  "created_at": "2026-10-08T15:00:00",
  "updated_at": "2026-10-08T15:00:05"
}
```

**Possible `status` values:**

| Status | Meaning |
|---|---|
| `pending` | Job created, processing hasn't started |
| `processing` | Certificates are being generated |
| `completed` | All certificates generated successfully |
| `completed_with_errors` | Some certificates failed (check individual statuses) |

### 3. List Certificates for a Job

**`GET /api/jobs/{job_id}/certificates`**

Optionally filter by status: `?status=success`, `?status=failed`, or `?status=pending`.

**Response (`200 OK`):**

```json
{
  "job_id": "a1b2c3d4-...",
  "certificates": [
    {
      "id": "cert-uuid-1",
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "status": "success",
      "error_message": null,
      "download_url": "/api/certificates/cert-uuid-1/download"
    },
    {
      "id": "cert-uuid-2",
      "recipient_name": "Bad Data",
      "recipient_email": "bad@example.com",
      "status": "failed",
      "error_message": "Font rendering error",
      "download_url": null
    }
  ]
}
```

### 4. Download a Certificate

**`GET /api/certificates/{certificate_id}/download`**

Returns the generated PDF file. Only available for certificates with `status: "success"`.

**Response:** PDF file (`application/pdf`)

**cURL Example:**

```bash