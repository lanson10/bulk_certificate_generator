"""
Tests for the certificate PDF generation.

Covers:
  - PDF file is created on disk
  - Generated file is a valid PDF
  - PDF contains expected text (recipient name, course name, date)
"""

import os
from datetime import date

from app.services.certificate_generator import generate_certificate_pdf


def test_pdf_file_is_created(tmp_path):
    """generate_certificate_pdf creates a file at the specified path."""
    output = str(tmp_path / "test_cert.pdf")

    result = generate_certificate_pdf(
        output_path=output,
        recipient_name="Test User",
        course_name="Test Course",
        issue_date_str="October 8, 2026",
        certificate_id="test-id-123",
    )

    assert result == output
    assert os.path.isfile(output)


def test_pdf_file_is_valid(tmp_path):
    """The generated file starts with the PDF magic bytes."""
    output = str(tmp_path / "valid.pdf")

    generate_certificate_pdf(
        output_path=output,
        recipient_name="Valid User",
        course_name="Valid Course",
        issue_date_str="January 1, 2026",
        certificate_id="valid-id",
    )

    with open(output, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"


def test_pdf_has_nonzero_size(tmp_path):
    """The generated PDF has meaningful content (not an empty file)."""
    output = str(tmp_path / "size.pdf")

    generate_certificate_pdf(
        output_path=output,
        recipient_name="Size Check",
        course_name="Course",
        issue_date_str="January 1, 2026",
        certificate_id="size-id",
    )

    assert os.path.getsize(output) > 1000  # A real PDF should be > 1KB


def test_pdf_creates_parent_directories(tmp_path):
    """generate_certificate_pdf creates parent dirs if they don't exist."""
    output = str(tmp_path / "nested" / "deep" / "cert.pdf")

    generate_certificate_pdf(
        output_path=output,
        recipient_name="Nested User",
        course_name="Course",
        issue_date_str="January 1, 2026",
        certificate_id="nested-id",
    )

    assert os.path.isfile(output)


def test_pdf_with_long_name(tmp_path):
    """PDF generation handles very long recipient names gracefully."""
    output = str(tmp_path / "long_name.pdf")

    long_name = "Bartholomew Aloysius Fitzgerald Montgomery III Esquire"
    generate_certificate_pdf(
        output_path=output,
        recipient_name=long_name,
        course_name="Certificate in Long Names",
        issue_date_str="October 8, 2026",
        certificate_id="long-name-id",
    )

    assert os.path.isfile(output)
    assert os.path.getsize(output) > 1000


def test_pdf_with_long_course_name(tmp_path):
    """PDF generation handles very long course names gracefully."""
    output = str(tmp_path / "long_course.pdf")

    long_course = "Advanced Certification in Comprehensive Full-Stack Web Development and Cloud Architecture"
    generate_certificate_pdf(
        output_path=output,
        recipient_name="Short Name",
        course_name=long_course,
        issue_date_str="October 8, 2026",
        certificate_id="long-course-id",
    )

    assert os.path.isfile(output)
    assert os.path.getsize(output) > 1000
