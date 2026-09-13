"""
NEXUS — SQLAlchemy ORM Models.

Re-exports every model and the shared ``Base`` so that the rest of the
application can do::

    from app.models import Base, User, JobListing, Resume, ...
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all NEXUS models."""

    pass


# ── Re-export every model so Alembic / init_db can discover them ─────
from app.models.user import User  # noqa: E402, F401
from app.models.job_listing import JobListing  # noqa: E402, F401
from app.models.resume import Resume  # noqa: E402, F401
from app.models.user_listing_match import UserListingMatch  # noqa: E402, F401
from app.models.briefing_job import BriefingJob  # noqa: E402, F401
from app.models.token_usage import TokenUsage  # noqa: E402, F401

__all__ = [
    "Base",
    "User",
    "JobListing",
    "Resume",
    "UserListingMatch",
    "BriefingJob",
    "TokenUsage",
]
