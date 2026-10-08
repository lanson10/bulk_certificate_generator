"""
Pydantic schemas for request validation and response serialization.

Validation rules:
  - course_name: required, 1–200 characters
  - issue_date:  required, valid date
  - recipients:  required, 1–MAX_RECIPIENTS_PER_JOB entries, no duplicate emails
  - name:        required, 1–150 characters
  - email:       required, valid email format
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.config import MAX_RECIPIENTS_PER_JOB


# ── Request Schemas ──────────────────────────────────────────────────────────


class RecipientIn(BaseModel):
    """A single recipient in a certificate generation request."""

    name: str = Field(
        ..., min_length=1, max_length=150, description="Recipient's full name"
    )
    email: EmailStr = Field(..., description="Recipient's email address")


class JobCreateRequest(BaseModel):
    """Request body for creating a bulk certificate generation job."""

    course_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the course or event",
    )
    issue_date: date = Field(
        ..., description="Date to print on the certificates"
    )
    recipients: List[RecipientIn] = Field(
        ...,
        min_length=1,
        max_length=MAX_RECIPIENTS_PER_JOB,
        description=f"List of recipients (1–{MAX_RECIPIENTS_PER_JOB})",
    )

    @model_validator(mode="after")
    def check_no_duplicate_emails(self) -> "JobCreateRequest":
        emails = [r.email.lower() for r in self.recipients]
        duplicates = {e for e in emails if emails.count(e) > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate recipient emails found: {', '.join(sorted(duplicates))}"
            )
        return self


# ── Response Schemas ─────────────────────────────────────────────────────────


class JobCreateResponse(BaseModel):
    """Returned when a new job is successfully created."""

    job_id: str
    status: str
    total_count: int
    message: str


class JobStatusResponse(BaseModel):
    """Full status view of a generation job."""

    id: str
    course_name: str
    issue_date: date
    status: str
    total_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CertificateResponse(BaseModel):
    """Status of an individual certificate within a job."""

    id: str
    recipient_name: str
    recipient_email: str
    status: str
    error_message: Optional[str] = None
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class CertificateListResponse(BaseModel):
    """List of certificates belonging to a job."""

    job_id: str
    certificates: List[CertificateResponse]


class JobListResponse(BaseModel):
    """Paginated list of all jobs."""

    jobs: List[JobStatusResponse]
    total: int
