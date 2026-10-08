"""
Tests for job status and progress tracking.

Covers:
  - Polling job status after creation
  - Status transitions (pending → processing → completed)
  - Progress counters (success_count, failure_count)
  - 404 for non-existent job
  - Listing all jobs
"""

import time

from app.models import Job, JobStatus


def test_job_status_after_creation(client, sample_request, certificates_dir):
    """
    After creation, the job should eventually reach 'completed' status.
    Since TestClient runs background tasks synchronously, the job should
    be completed by the time we query it.
    """
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200

    data = status_resp.json()
    assert data["id"] == job_id
    assert data["course_name"] == "Advanced Python Workshop"
    assert data["status"] in ("completed", "processing", "pending")
    assert data["total_count"] == 3


def test_job_completed_with_correct_counts(
    client, sample_request, certificates_dir
):
    """After background processing, success_count should equal total_count."""
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    # TestClient runs BackgroundTasks synchronously, so the job is done
    status_resp = client.get(f"/api/jobs/{job_id}")
    data = status_resp.json()

    assert data["status"] == "completed"
    assert data["success_count"] == 3
    assert data["failure_count"] == 0


def test_job_not_found(client):
    """GET /api/jobs/<non-existent> returns 404."""
    response = client.get("/api/jobs/non-existent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_jobs(client, sample_request, certificates_dir):
    """GET /api/jobs returns a list containing the created job."""
    client.post("/api/jobs", json=sample_request)

    response = client.get("/api/jobs")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 1
    assert len(data["jobs"]) >= 1
    assert data["jobs"][0]["course_name"] == "Advanced Python Workshop"


def test_list_jobs_empty(client):
    """GET /api/jobs returns an empty list when no jobs exist."""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["jobs"] == []


def test_job_status_response_shape(client, sample_request, certificates_dir):
    """The status response includes all expected fields."""
    create_resp = client.post("/api/jobs", json=sample_request)
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/api/jobs/{job_id}")
    data = status_resp.json()

    required_fields = [
        "id", "course_name", "issue_date", "status",
        "total_count", "success_count", "failure_count",
        "created_at", "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_list_jobs_pagination(client, certificates_dir):
    """GET /api/jobs respects skip and limit query parameters."""
    for i in range(5):
        payload = {
            "course_name": f"Course {i}",
            "issue_date": "2026-01-01",
            "recipients": [{"name": f"User {i}", "email": f"user{i}@example.com"}],
        }
        client.post("/api/jobs", json=payload)

    # Fetch with limit=2
    resp = client.get("/api/jobs?skip=0&limit=2")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["jobs"]) == 2

    # Fetch with skip=4, limit=2
    resp_skip = client.get("/api/jobs?skip=4&limit=2")
    data_skip = resp_skip.json()
    assert data_skip["total"] == 5
    assert len(data_skip["jobs"]) == 1


def test_health_check(client):
    """GET / returns 200 with service info."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dashboard_endpoint(client):
    """GET /dashboard returns 200 and the HTML dashboard."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "CertiCraft" in resp.text


def test_html_root_endpoint(client):
    """GET / with text/html Accept header returns dashboard HTML."""
    resp = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "CertiCraft" in resp.text
