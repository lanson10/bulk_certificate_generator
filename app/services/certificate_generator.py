"""
PDF certificate generator using ReportLab.

Produces a single-page A4 landscape PDF with:
  - Decorative border
  - "Certificate of Completion" title
  - Recipient name, course name, and issue date
  - Unique certificate ID for verification

This is a pure function: it takes data in and writes a PDF file to disk.
It has no dependency on the database or web framework.
"""

import os
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas


# ── Colour palette ───────────────────────────────────────────────────────────

_NAVY = HexColor("#1a2744")
_GOLD = HexColor("#c9a84c")
_DARK_GRAY = HexColor("#333333")
_MEDIUM_GRAY = HexColor("#666666")
_LIGHT_GOLD = HexColor("#f5e6b8")


def generate_certificate_pdf(
    output_path: str,
    recipient_name: str,
    course_name: str,
    issue_date_str: str,
    certificate_id: str,
) -> str:
    """
    Generate a certificate PDF and save it to *output_path*.

    Args:
        output_path:     Absolute path where the PDF will be written.
        recipient_name:  Name printed on the certificate.
        course_name:     Course or event name.
        issue_date_str:  Human-readable date string (e.g. "October 8, 2026").
        certificate_id:  Unique ID printed at the bottom for verification.

    Returns:
        The *output_path* on success.

    Raises:
        Any exception from ReportLab or the filesystem (e.g. IOError).
    """
    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    page_width, page_height = landscape(A4)
    c = canvas.Canvas(output_path, pagesize=landscape(A4))

    # ── Background ───────────────────────────────────────────────────────
    c.setFillColor(HexColor("#fdfbf5"))
    c.rect(0, 0, page_width, page_height, fill=True, stroke=False)

    # ── Outer border ─────────────────────────────────────────────────────
    margin = 0.4 * inch
    c.setStrokeColor(_NAVY)
    c.setLineWidth(3)
    c.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)

    # ── Inner border ─────────────────────────────────────────────────────
    inner_margin = 0.6 * inch
    c.setStrokeColor(_GOLD)
    c.setLineWidth(1.5)
    c.rect(
        inner_margin,
        inner_margin,
        page_width - 2 * inner_margin,
        page_height - 2 * inner_margin,
    )

    # ── Corner accents (small gold squares) ──────────────────────────────
    accent_size = 8
    for x in [inner_margin, page_width - inner_margin - accent_size]:
        for y in [inner_margin, page_height - inner_margin - accent_size]:
            c.setFillColor(_GOLD)
            c.rect(x, y, accent_size, accent_size, fill=True, stroke=False)

    # ── Decorative top line ──────────────────────────────────────────────
    centre_x = page_width / 2
    top_y = page_height - 1.3 * inch
    line_width = 3 * inch
    c.setStrokeColor(_GOLD)
    c.setLineWidth(1)
    c.line(centre_x - line_width / 2, top_y, centre_x + line_width / 2, top_y)

    # ── Title ────────────────────────────────────────────────────────────
    c.setFillColor(_NAVY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(centre_x, top_y + 0.35 * inch, "CERTIFICATE")

    c.setFont("Helvetica", 28)
    c.drawCentredString(centre_x, top_y - 0.45 * inch, "Certificate of Completion")

    # ── Decorative line below title ──────────────────────────────────────
    c.setStrokeColor(_GOLD)
    c.line(
        centre_x - line_width / 2,
        top_y - 0.7 * inch,
        centre_x + line_width / 2,
        top_y - 0.7 * inch,
    )

    # ── "This is to certify that" ────────────────────────────────────────
    c.setFillColor(_MEDIUM_GRAY)
    c.setFont("Helvetica", 12)
    c.drawCentredString(centre_x, top_y - 1.15 * inch, "This is to certify that")

    # ── Recipient name ───────────────────────────────────────────────────
    c.setFillColor(_NAVY)
    # Scale font down for very long names
    name_font_size = 30 if len(recipient_name) <= 30 else 22
    c.setFont("Helvetica-Bold", name_font_size)
    c.drawCentredString(centre_x, top_y - 1.65 * inch, recipient_name)

    # Underline beneath name
    name_width = min(
        c.stringWidth(recipient_name, "Helvetica-Bold", name_font_size) + 40,
        page_width - 4 * inch,
    )
    c.setStrokeColor(_LIGHT_GOLD)
    c.setLineWidth(0.8)
    c.line(
        centre_x - name_width / 2,
        top_y - 1.75 * inch,
        centre_x + name_width / 2,
        top_y - 1.75 * inch,
    )

    # ── "has successfully completed" ─────────────────────────────────────
    c.setFillColor(_MEDIUM_GRAY)
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        centre_x, top_y - 2.15 * inch, "has successfully completed the course"
    )

    # ── Course name ──────────────────────────────────────────────────────
    c.setFillColor(_DARK_GRAY)
    course_font_size = 20 if len(course_name) <= 40 else 16
    c.setFont("Helvetica-Bold", course_font_size)
    c.drawCentredString(centre_x, top_y - 2.6 * inch, course_name)

    # ── Date ─────────────────────────────────────────────────────────────
    c.setFillColor(_MEDIUM_GRAY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(
        centre_x, top_y - 3.15 * inch, f"Issued on {issue_date_str}"
    )

    # ── Bottom decorative line ───────────────────────────────────────────
    bottom_line_y = 1.0 * inch
    c.setStrokeColor(_GOLD)
    c.line(
        centre_x - line_width / 2,
        bottom_line_y,
        centre_x + line_width / 2,
        bottom_line_y,
    )

    # ── Certificate ID ───────────────────────────────────────────────────
    c.setFillColor(_MEDIUM_GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        centre_x, 0.7 * inch, f"Certificate ID: {certificate_id}"
    )

    c.save()
    return output_path
