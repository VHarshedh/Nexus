"""
NEXUS — Token Usage and Cost Tracking Model.

Records token consumption and financial expenditure (in USD and INR)
across various LLM features in NEXUS.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class TokenUsage(Base):
    __tablename__ = "token_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    feature: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # e.g., 'career_agent', 'resume_parsing', 'match_justifications', 'video_briefing', 'job_extraction'
    model: Mapped[str] = mapped_column(
        String(64), nullable=False, default="gemini-3.5-flash-lite"
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    cost_usd: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    cost_inr: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User | None"] = relationship(  # type: ignore[name-defined]
        back_populates="token_usages"
    )

    def __repr__(self) -> str:
        return (
            f"<TokenUsage feature={self.feature} tokens={self.total_tokens} "
            f"inr=₹{self.cost_inr:.4f}>"
        )
