"""
NEXUS — BriefingJob Model.

Tracks asynchronous "career briefing" generation jobs — each job produces an
AI-generated script and (optionally) a media asset for the user.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class BriefingJob(Base):
    __tablename__ = "briefing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False,
        comment="queued | generating_script | synthesizing_media | done | failed",
    )
    script: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(2048))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="briefing_jobs")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<BriefingJob {self.id} status={self.status}>"
