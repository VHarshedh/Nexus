"""
NEXUS — UserListingMatch Model.

Records the match between a user's resume and a job listing, including a
numeric score, an LLM-generated justification, and workflow status flags.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class UserListingMatch(Base):
    __tablename__ = "user_listing_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    justification: Mapped[str | None] = mapped_column(Text)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False,
        comment="pending | reviewed | applied | rejected",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="matches")  # type: ignore[name-defined]
    listing: Mapped["JobListing"] = relationship()  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<UserListingMatch score={self.match_score:.2f}>"
