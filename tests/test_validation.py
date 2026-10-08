"""
Tests for input validation.

Covers:
  - Missing required fields
  - Empty recipients list
  - Invalid email format
  - Duplicate emails within a request
  - Field length limits
  - Invalid date format
"""


def test_missing_course_name(client):
    """course_name is required."""
    payload = {
        "issue_date": "2026-01-01",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_empty_course_name(client):
    """course_name cannot be an empty string."""
    payload = {
        "course_name": "",
        "issue_date": "2026-01-01",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_missing_issue_date(client):
    """issue_date is required."""
    payload = {
        "course_name": "Test Course",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_invalid_date_format(client):
    """issue_date must be a valid date."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "not-a-date",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_missing_recipients(client):
    """recipients list is required."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_empty_recipients_list(client):
    """recipients list cannot be empty."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_invalid_email_format(client):
    """Recipient email must be a valid email."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [{"name": "Alice", "email": "not-an-email"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_missing_recipient_name(client):
    """Recipient name is required."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [{"email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_empty_recipient_name(client):
    """Recipient name cannot be empty."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [{"name": "", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_duplicate_emails_rejected(client):
    """Duplicate emails within the same request are rejected."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "Alice Again", "email": "alice@example.com"},
        ],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422
    # The error should mention duplicate emails
    assert "duplicate" in response.json()["detail"][0]["msg"].lower()


def test_course_name_too_long(client):
    """course_name is limited to 200 characters."""
    payload = {
        "course_name": "X" * 201,
        "issue_date": "2026-01-01",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_recipient_name_too_long(client):
    """Recipient name is limited to 150 characters."""
    payload = {
        "course_name": "Test Course",
        "issue_date": "2026-01-01",
        "recipients": [{"name": "A" * 151, "email": "alice@example.com"}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_completely_empty_body(client):
    """An empty request body is rejected."""
    response = client.post("/api/jobs", json={})
    assert response.status_code == 422
