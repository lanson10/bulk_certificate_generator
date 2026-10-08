"""
Tests for creating a certificate generation job.

Covers:
  - Successful job creation returns 202 with correct shape
  - Job is persisted in the database with correct counts
  - Certificate records are created for each recipient
"""

from app.models import Certificate, Job


def test_create_job_returns_202(client, sample_request, certificates_dir):
    """POST /api/jobs returns 202 Accepted with job details."""
    response = client.post("/api/jobs", json=sample_request)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["total_count"] == 3
    assert "message" in data


def test_create_job_persists_job(client, sample_request, db_session, certificates_dir):
    """The job record is persisted in the DB with correct metadata."""
    response = client.post("/api/jobs", json=sample_request)
    job_id = response.json()["job_id"]

    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert job.course_name == "Advanced Python Workshop"
    assert job.total_count == 3


def test_create_job_persists_certificates(
    client, sample_request, db_session, certificates_dir
):
    """A certificate record is created for each recipient."""
    response = client.post("/api/jobs", json=sample_request)
    job_id = response.json()["job_id"]

    certs = (
        db_session.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .all()
    )
    assert len(certs) == 3
    names = {c.recipient_name for c in certs}
    assert names == {"Alice Johnson", "Bob Smith", "Charlie Brown"}


def test_create_job_single_recipient(client, certificates_dir):
    """A job with a single recipient is valid."""
    payload = {
        "course_name": "Solo Course",
        "issue_date": "2026-01-01",
        "recipients": [{"name": "Solo Person", "email": "solo@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    assert response.json()["total_count"] == 1


def test_create_job_from_csv_success(client, certificates_dir):
    """POST /api/jobs/upload-csv accepts a CSV file and generates certificates."""
    csv_content = b"name,email\nDiana Prince,diana@example.com\nBruce Wayne,bruce@example.com\n"
    files = {"file": ("recipients.csv", csv_content, "text/csv")}
    data = {
        "course_name": "Justice Training",
        "issue_date": "2026-05-15",
    }
    response = client.post("/api/jobs/upload-csv", data=data, files=files)
    assert response.status_code == 202
    body = response.json()
    assert body["total_count"] == 2
    assert "job_id" in body


def test_create_job_from_csv_invalid_extension(client):
    """Uploading a non-csv file returns 400."""
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    data = {"course_name": "Test", "issue_date": "2026-01-01"}
    response = client.post("/api/jobs/upload-csv", data=data, files=files)
    assert response.status_code == 400
    assert "csv files are supported" in response.json()["detail"].lower()


def test_create_job_from_csv_empty(client):
    """Uploading an empty CSV file returns 400."""
    files = {"file": ("empty.csv", b"", "text/csv")}
    data = {"course_name": "Test", "issue_date": "2026-01-01"}
    response = client.post("/api/jobs/upload-csv", data=data, files=files)
    assert response.status_code == 400


def test_create_job_from_csv_duplicate_emails(client):
    """CSV containing duplicate emails is rejected with 422."""
    csv_content = b"name,email\nUser 1,dup@example.com\nUser 2,dup@example.com\n"
    files = {"file": ("recipients.csv", csv_content, "text/csv")}
    data = {"course_name": "Test", "issue_date": "2026-01-01"}
    response = client.post("/api/jobs/upload-csv", data=data, files=files)
    assert response.status_code == 422
