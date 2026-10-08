"""
Background job processor for bulk certificate generation.

Design decisions:
  - Uses a ThreadPoolExecutor so that PDF generation (CPU + I/O bound) runs
    in parallel across multiple threads without blocking the API event loop.
  - Each certificate is processed independently: a failure in one certificate
    does NOT prevent the others from being generated.
  - Job-level status is updated atomically after all certificates are processed:
      • "completed"             — every certificate succeeded
      • "completed_with_errors" — at least one failed

Why ThreadPoolExecutor instead of Celery?
  - No external infrastructure required (no Redis, no RabbitMQ).
  - Sufficient for the single-server deployment scope of this project.
  - If horizontal scaling were needed later, swapping to Celery would be
    a localised change in this module only.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.config import CERTIFICATES_DIR, WORKER_POOL_SIZE
from app.database import SessionLocal
from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.services.certificate_generator import generate_certificate_pdf

logger = logging.getLogger(__name__)

# Module-level thread pool — created once, reused across requests.
_executor = ThreadPoolExecutor(max_workers=WORKER_POOL_SIZE)


def get_executor() -> ThreadPoolExecutor:
    """Return the module-level executor (useful for testing / shutdown)."""
    return _executor


def shutdown_executor() -> None:
    """Gracefully shut down the thread pool and recreate it for reuse."""
    global _executor
    _executor.shutdown(wait=True)
    _executor = ThreadPoolExecutor(max_workers=WORKER_POOL_SIZE)


# ── Public entry point ───────────────────────────────────────────────────────


def process_job(job_id: str) -> None:
    """
    Process all pending certificates for the given job.

    This function is intended to be called from a background thread (via
    FastAPI's BackgroundTasks). It opens its own DB session so it is
    fully independent of the request lifecycle.
    """
    db: Session = SessionLocal()
    try:
        _run_job(db, job_id)
    except Exception:
        logger.exception("Unexpected error processing job %s", job_id)
        # Try to mark the job as errored
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.COMPLETED_WITH_ERRORS
                db.commit()
        except Exception:
            logger.exception("Failed to update job status for %s", job_id)
    finally:
        db.close()


# ── Internal implementation ──────────────────────────────────────────────────


def _run_job(db: Session, job_id: str) -> None:
    """Core processing loop for a single job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        logger.error("Job %s not found", job_id)
        return

    # Transition job to processing
    job.status = JobStatus.PROCESSING
    db.commit()

    certificates = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .all()
    )

    # Submit all certificate generations to the thread pool
    future_to_cert_id = {}
    for cert in certificates:
        future = _executor.submit(
            _generate_single_certificate,
            cert_id=cert.id,
            recipient_name=cert.recipient_name,
            course_name=job.course_name,
            issue_date=job.issue_date,
        )
        future_to_cert_id[future] = cert.id

    # Collect results as they complete
    success_count = 0
    failure_count = 0

    for future in as_completed(future_to_cert_id):
        cert_id = future_to_cert_id[future]
        cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
        if not cert:
            continue

        try:
            file_path = future.result()
            cert.status = CertificateStatus.SUCCESS
            cert.file_path = file_path
            success_count += 1
        except Exception as exc:
            cert.status = CertificateStatus.FAILED
            cert.error_message = str(exc)[:500]  # Truncate long errors
            failure_count += 1
            logger.warning(
                "Certificate %s failed: %s", cert_id, exc, exc_info=True
            )

        db.commit()

    # Finalise job status
    job.success_count = success_count
    job.failure_count = failure_count
    if failure_count == 0:
        job.status = JobStatus.COMPLETED
    else:
        job.status = JobStatus.COMPLETED_WITH_ERRORS
    db.commit()

    logger.info(
        "Job %s finished: %d/%d succeeded, %d failed",
        job_id,
        success_count,
        job.total_count,
        failure_count,
    )


def _generate_single_certificate(
    cert_id: str,
    recipient_name: str,
    course_name: str,
    issue_date,
) -> str:
    """
    Generate a single certificate PDF.

    Runs inside a thread pool worker. Returns the file path on success,
    or raises on failure.
    """
    # Format date for display
    issue_date_str = issue_date.strftime("%B %d, %Y")

    # Build output path: certificates/<cert_id>.pdf
    filename = f"{cert_id}.pdf"
    output_path = os.path.join(CERTIFICATES_DIR, filename)

    generate_certificate_pdf(
        output_path=output_path,
        recipient_name=recipient_name,
        course_name=course_name,
        issue_date_str=issue_date_str,
        certificate_id=cert_id,
    )

    return output_path
