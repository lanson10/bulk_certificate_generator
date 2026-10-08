"""
API route handlers for certificate generation jobs.

Endpoints:
  POST   /api/jobs                          — Create a new generation job
  GET    /api/jobs                          — List all jobs
  GET    /api/jobs/{job_id}                 — Get job status / progress
  GET    /api/jobs/{job_id}/certificates    — List certificates for a job
  GET    /api/certificates/{certificate_id}/download — Download a certificate PDF
"""

import csv
import io
import os
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CertificateStatus
from app.schemas import (
    CertificateListResponse,
    CertificateResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobListResponse,
    JobStatusResponse,
    RecipientIn,
)
from app.services import job_service
from app.services.job_processor import process_job

router = APIRouter(prefix="/api", tags=["jobs"])


# ── POST /api/jobs ───────────────────────────────────────────────────────────


@router.post("/jobs", response_model=JobCreateResponse, status_code=202)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a bulk certificate generation job.

    Validates the request, persists the job and certificate records,
    then kicks off background processing. Returns immediately with a
    202 Accepted response so the client can poll for progress.
    """
    job = job_service.create_job(db, request)

    # Schedule background processing
    background_tasks.add_task(process_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status.value,
        total_count=job.total_count,
        message="Job created. Certificates are being generated in the background.",
    )


# ── POST /api/jobs/upload-csv ───────────────────────────────────────────────


@router.post("/jobs/upload-csv", response_model=JobCreateResponse, status_code=202)
async def create_job_from_csv(
    background_tasks: BackgroundTasks,
    course_name: str = Form(..., min_length=1, max_length=200),
    issue_date: date = Form(...),
    file: UploadFile = File(..., description="CSV file with name and email"),
    db: Session = Depends(get_db),
):
    """
    Create a bulk certificate generation job directly from an uploaded CSV file.

    Accepts multipart/form-data with course_name, issue_date, and file (.csv).
    Automatically identifies name and email columns.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content_bytes = await file.read()
    text = content_bytes.decode("utf-8-sig", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if not lines:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in CSV")

    # Detect header row
    header = [c.lower().strip() for c in rows[0]]
    has_name = any("name" in c for c in header)
    has_email = any("email" in c or "mail" in c for c in header)

    if has_name and has_email:
        name_idx = next(i for i, c in enumerate(header) if "name" in c)
        email_idx = next(i for i, c in enumerate(header) if "email" in c or "mail" in c)
        data_rows = rows[1:]
    else:
        name_idx = 0
        email_idx = 1
        data_rows = rows

    recipients = []
    for r in data_rows:
        if len(r) > max(name_idx, email_idx):
            name = r[name_idx].strip()
            email = r[email_idx].strip()
            if name and email:
                recipients.append(RecipientIn(name=name, email=email))

    if not recipients:
        raise HTTPException(
            status_code=400, detail="No valid recipient rows found in CSV"
        )

    try:
        job_request = JobCreateRequest(
            course_name=course_name,
            issue_date=issue_date,
            recipients=recipients,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job = job_service.create_job(db, job_request)
    background_tasks.add_task(process_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status.value,
        total_count=job.total_count,
        message="Job created from CSV. Certificates are being generated in the background.",
    )


# ── GET /api/jobs ────────────────────────────────────────────────────────────


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max jobs to return"),
    db: Session = Depends(get_db),
):
    """List all generation jobs, newest first."""
    jobs, total = job_service.list_jobs(db, skip=skip, limit=limit)
    return JobListResponse(
        jobs=[JobStatusResponse.model_validate(j) for j in jobs],
        total=total,
    )


# ── GET /api/jobs/{job_id} ───────────────────────────────────────────────────


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get the current status and progress of a generation job."""
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse.model_validate(job)


# ── GET /api/jobs/{job_id}/certificates ──────────────────────────────────────


@router.get(
    "/jobs/{job_id}/certificates", response_model=CertificateListResponse
)
def list_certificates(
    job_id: str,
    status: Optional[str] = Query(
        None,
        description="Filter by status: pending, success, or failed",
    ),
    db: Session = Depends(get_db),
):
    """
    List all certificates belonging to a job.

    Optionally filter by status (pending / success / failed).
    """
    # Verify the job exists
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Validate the status filter value if provided
    if status is not None:
        valid_statuses = {s.value for s in CertificateStatus}
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter. Must be one of: {', '.join(sorted(valid_statuses))}",
            )

    certificates = job_service.get_certificates_for_job(
        db, job_id, status_filter=status
    )

    cert_responses = []
    for cert in certificates:
        download_url = None
        if cert.status == CertificateStatus.SUCCESS:
            download_url = f"/api/certificates/{cert.id}/download"
        cert_responses.append(
            CertificateResponse(
                id=cert.id,
                recipient_name=cert.recipient_name,
                recipient_email=cert.recipient_email,
                status=cert.status.value,
                error_message=cert.error_message,
                download_url=download_url,
            )
        )

    return CertificateListResponse(job_id=job_id, certificates=cert_responses)


# ── GET /api/certificates/{certificate_id}/download ─────────────────────────


@router.get("/certificates/{certificate_id}/download")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """
    Download a generated certificate PDF.

    Returns 404 if the certificate doesn't exist, hasn't been generated yet,
    or the file is missing from disk.
    """
    cert = job_service.get_certificate(db, certificate_id)

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if cert.status != CertificateStatus.SUCCESS:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate not available. Current status: {cert.status.value}",
        )

    if not cert.file_path or not os.path.isfile(cert.file_path):
        raise HTTPException(
            status_code=404, detail="Certificate file not found on disk"
        )

    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=f"certificate_{cert.recipient_name.replace(' ', '_')}_{cert.id[:8]}.pdf",
    )
