"""
SQLAlchemy ORM models for the certificate generation system.

Two tables:
  - jobs:         Represents a bulk certificate generation request.
  - certificates: Represents an individual certificate within a job.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    """Lifecycle states for a generation job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"


class CertificateStatus(str, enum.Enum):
    """Lifecycle states for an individual certificate."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    course_name = Column(String(200), nullable=False)
    issue_date = Column(Date, nullable=False)
    total_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING
    )
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    certificates = relationship(
        "Certificate", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} [{self.status}]>"


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    recipient_name = Column(String(150), nullable=False)
    recipient_email = Column(String(254), nullable=False)
    status = Column(
        Enum(CertificateStatus),
        nullable=False,
        default=CertificateStatus.PENDING,
    )
    error_message = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    job = relationship("Job", back_populates="certificates")

    def __repr__(self) -> str:
        return f"<Certificate {self.id} for '{self.recipient_name}' [{self.status}]>"
