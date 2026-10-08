"""
Tests for retrieving / downloading generated certificates.

Covers:
  - Downloading a successfully generated certificate
  - 404 for non-existent certificate
  - 404 for a certificate that hasn't been generated yet (still pending)
  - Correct Content-Type header (application/pdf)
  - Certificate list includes download URLs for successful certificates
"""


def test_download_successful_certificate(client, sample_request, certificates_dir):
    """A successfully generated certificate can be downloaded as a PDF."""
    # Create a job and wait for processing
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    # Get the list of certificates
    certs_resp = client.get(f"/api/jobs/{job_id}/certificates")
    certs = certs_resp.json()["certificates"]

    # Find a successful one
    success_cert = next(c for c in certs if c["status"] == "success")
    assert success_cert["download_url"] is not None

    # Download it
    download_resp = client.get(success_cert["download_url"])
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    # Verify it's a real PDF
    assert download_resp.content[:5] == b"%PDF-"


def test_download_nonexistent_certificate(client):
    """Downloading a certificate that doesn't exist returns 404."""
    response = client.get("/api/certificates/nonexistent-id/download")
    assert response.status_code == 404


def test_download_pending_certificate(client, db_session, certificates_dir):
    """
    Downloading a certificate that is still pending returns 404
    with a meaningful message.
    """
    from app.models import Certificate, CertificateStatus, Job, JobStatus
    from datetime import date, datetime, timezone

    # Create a job and certificate directly in the DB (bypass processing)
    job = Job(
        id="test-job-pending",
        course_name="Test",
        issue_date=date(2026, 1, 1),
        total_count=1,
        status=JobStatus.PROCESSING,
    )
    db_session.add(job)
    db_session.flush()

    cert = Certificate(
        id="test-cert-pending",
        job_id=job.id,
        recipient_name="Pending Person",
        recipient_email="pending@example.com",
        status=CertificateStatus.PENDING,
    )
    db_session.add(cert)
    db_session.commit()

    response = client.get("/api/certificates/test-cert-pending/download")
    assert response.status_code == 404
    assert "pending" in response.json()["detail"].lower()


def test_certificate_list_has_download_urls(
    client, sample_request, certificates_dir
):
    """Successful certificates in the list should have download_url set."""
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    certs_resp = client.get(f"/api/jobs/{job_id}/certificates")
    certs = certs_resp.json()["certificates"]

    for cert in certs:
        if cert["status"] == "success":
            assert cert["download_url"] is not None
            assert cert["download_url"].startswith("/api/certificates/")
        elif cert["status"] in ("pending", "failed"):
            assert cert["download_url"] is None


def test_certificates_for_nonexistent_job(client):
    """Listing certificates for a non-existent job returns 404."""
    response = client.get("/api/jobs/fake-job-id/certificates")
    assert response.status_code == 404


def test_invalid_status_filter(client, sample_request, certificates_dir):
    """An invalid status filter value returns 400."""
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/certificates?status=invalid")
    assert response.status_code == 400


def test_download_missing_file_on_disk(client, db_session):
    """If a certificate is marked SUCCESS but file is removed, download returns 404."""
    from app.models import Certificate, CertificateStatus, Job, JobStatus
    from datetime import date

    job = Job(
        id="test-job-missing-file",
        course_name="Test",
        issue_date=date(2026, 1, 1),
        total_count=1,
        status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    db_session.flush()

    cert = Certificate(
        id="test-cert-missing-file",
        job_id=job.id,
        recipient_name="Ghost User",
        recipient_email="ghost@example.com",
        status=CertificateStatus.SUCCESS,
        file_path="/tmp/non_existent_file_path_12345.pdf",
    )
    db_session.add(cert)
    db_session.commit()

    response = client.get("/api/certificates/test-cert-missing-file/download")
    assert response.status_code == 404
    assert "not found on disk" in response.json()["detail"].lower()
