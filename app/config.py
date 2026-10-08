"""
Application configuration.

Uses Pydantic BaseSettings so values can be overridden via environment
variables (e.g. DATABASE_URL, CERTIFICATES_DIR).
"""

import os
from pathlib import Path


# Base directory of the project (one level up from app/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Directory where generated certificate PDFs are stored
CERTIFICATES_DIR = os.getenv("CERTIFICATES_DIR", str(BASE_DIR / "certificates"))

# SQLite database URL — file-based by default
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")

# Maximum number of recipients allowed in a single job request
MAX_RECIPIENTS_PER_JOB = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))

# Number of threads in the pool used for background certificate generation
WORKER_POOL_SIZE = int(os.getenv("WORKER_POOL_SIZE", "4"))
