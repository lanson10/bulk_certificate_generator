"""
Tests for individual certificate failure handling.

Covers:
  - One failed certificate does not block others in the same job
  - Job gets 'completed_with_errors' status on partial failure
  - Error messages are captured on the failed certificate
  - Success/failure counts are accurate
"""

from unittest.mock import patch

from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.services.job_processor import process_job


def test_partial_failure_does_not_block_others(
    client, db_session, certificates_dir
):
    """
    If one certificate fails during generation, the others should still
    be generated successfully.

    We simulate failure by patching the PDF generator to raise for one
    specific recipient name.
    """
    payload = {
        "course_name": "Failure Test Course",
        "issue_date": "2026-01-15",
        "recipients": [
            {"name": "Good User 1", "email": "good1@example.com"},
            {"name": "FAIL_THIS_ONE", "email": "fail@example.com"},
            {"name": "Good User 2", "email": "good2@example.com"},
        ],
    }


    with patch(
        "app.services.job_processor._generate_single_certificate"
    ) as mock_gen:
        # Make _generate_single_certificate fail for one recipient
        def side_effect(cert_id, recipient_name, course_name, issue_date):
            if recipient_name == "FAIL_THIS_ONE":
                raise RuntimeError("Simulated PDF generation failure")
            # Call the real implementation for other recipients
            from app.services.job_processor import _generate_single_certificate
            # We need to call the original, so let's just generate directly
            from app.services.certificate_generator import generate_certificate_pdf
            import os
            from app.config import CERTIFICATES_DIR
            issue_date_str = issue_date.strftime("%B %d, %Y")
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

        mock_gen.side_effect = side_effect

        response = client.post("/api/jobs", json=payload)

    job_id = response.json()["job_id"]

    # Check job status
    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "completed_with_errors"
    assert status["success_count"] == 2
    assert status["failure_count"] == 1

    # Check individual certificate statuses
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()["certificates"]
    statuses = {c["recipient_name"]: c["status"] for c in certs}

    assert statuses["Good User 1"] == "success"
    assert statuses["Good User 2"] == "success"
    assert statuses["FAIL_THIS_ONE"] == "failed"


def test_failed_certificate_has_error_message(
    client, db_session, certificates_dir
):
    """A failed certificate should have an error_message explaining what went wrong."""
    payload = {
        "course_name": "Error Message Test",
        "issue_date": "2026-01-15",
        "recipients": [
            {"name": "FAIL_THIS_ONE", "email": "fail@example.com"},
        ],
    }

    with patch(
        "app.services.job_processor._generate_single_certificate"
    ) as mock_gen:
        mock_gen.side_effect = RuntimeError("Font rendering error")
        response = client.post("/api/jobs", json=payload)

    job_id = response.json()["job_id"]
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()["certificates"]

    assert len(certs) == 1
    assert certs[0]["status"] == "failed"
    assert "Font rendering error" in certs[0]["error_message"]


def test_filter_certificates_by_status(client, db_session, certificates_dir):
    """The certificates endpoint supports filtering by status."""
    payload = {
        "course_name": "Filter Test",
        "issue_date": "2026-01-15",
        "recipients": [
            {"name": "Good User", "email": "good@example.com"},
            {"name": "FAIL_THIS_ONE", "email": "fail@example.com"},
        ],
    }

    with patch(
        "app.services.job_processor._generate_single_certificate"
    ) as mock_gen:
        def side_effect(cert_id, recipient_name, course_name, issue_date):
            if recipient_name == "FAIL_THIS_ONE":
                raise RuntimeError("Simulated failure")
            from app.services.certificate_generator import generate_certificate_pdf
            import os
            from app.config import CERTIFICATES_DIR
            issue_date_str = issue_date.strftime("%B %d, %Y")
            output_path = os.path.join(CERTIFICATES_DIR, f"{cert_id}.pdf")
            generate_certificate_pdf(
                output_path=output_path,
                recipient_name=recipient_name,
                course_name=course_name,
                issue_date_str=issue_date_str,
                certificate_id=cert_id,
            )
            return output_path

        mock_gen.side_effect = side_effect
        response = client.post("/api/jobs", json=payload)

    job_id = response.json()["job_id"]

    # Filter by success
    success_certs = client.get(
        f"/api/jobs/{job_id}/certificates?status=success"
    ).json()["certificates"]
    assert len(success_certs) == 1
    assert success_certs[0]["status"] == "success"

    # Filter by failed
    failed_certs = client.get(
        f"/api/jobs/{job_id}/certificates?status=failed"
    ).json()["certificates"]
    assert len(failed_certs) == 1
    assert failed_certs[0]["status"] == "failed"


def test_process_job_nonexistent_job(certificates_dir):
    """Calling process_job with a non-existent job ID exits safely without crashing."""
    import app.services.job_processor as processor
    from tests.conftest import TestSessionLocal

    orig = processor.SessionLocal
    processor.SessionLocal = TestSessionLocal
    try:
        # Should log error and return without raising
        processor.process_job("totally-fake-uuid")
    finally:
        processor.SessionLocal = orig


def test_process_job_catastrophic_exception_marks_job_error(db_session, certificates_dir):
    """If _run_job encounters a severe database or unexpected error, job is marked COMPLETED_WITH_ERRORS."""
    import app.services.job_processor as processor
    from tests.conftest import TestSessionLocal
    from datetime import date

    # Create job in DB
    job = Job(
        id="catastrophic-test-job",
        course_name="Crash Course",
        issue_date=date(2026, 1, 1),
        total_count=1,
        status=JobStatus.PENDING,
    )
    db_session.add(job)
    db_session.commit()

    orig = processor.SessionLocal
    processor.SessionLocal = TestSessionLocal
    try:
        with patch("app.services.job_processor._run_job", side_effect=RuntimeError("DB exploded")):
            processor.process_job("catastrophic-test-job")
    finally:
        processor.SessionLocal = orig

    updated_job = db_session.query(Job).filter(Job.id == "catastrophic-test-job").first()
    assert updated_job.status == JobStatus.COMPLETED_WITH_ERRORS
