"""
Business-logic service layer for certificate generation jobs.

Keeps the router thin — all DB interactions and orchestration live here.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas import JobCreateRequest


def create_job(db: Session, request: JobCreateRequest) -> Job:
    """
    Persist a new job and its associated certificate records.

    All certificates start in PENDING status and will be picked up
    by the background processor.
    """
    job = Job(
        course_name=request.course_name,
        issue_date=request.issue_date,
        total_count=len(request.recipients),
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()  # Assigns job.id so we can use it for certificates

    for recipient in request.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=str(recipient.email),
            status=CertificateStatus.PENDING,
        )
        db.add(cert)

    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Optional[Job]:
    """Retrieve a job by ID, or None if not found."""
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(db: Session, skip: int = 0, limit: int = 50) -> tuple:
    """Return a paginated list of jobs and the total count."""
    total = db.query(Job).count()
    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return jobs, total


def get_certificates_for_job(
    db: Session, job_id: str, status_filter: Optional[str] = None
) -> List[Certificate]:
    """
    Return all certificates for a job, optionally filtered by status.
    """
    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status_filter:
        query = query.filter(Certificate.status == status_filter)
    return query.order_by(Certificate.created_at).all()


def get_certificate(db: Session, certificate_id: str) -> Optional[Certificate]:
    """Retrieve a single certificate by ID."""
    return (
        db.query(Certificate).filter(Certificate.id == certificate_id).first()
    )
