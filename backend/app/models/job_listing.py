"""
NEXUS — JobListing Model.

Stores scraped job listings with LLM-extracted structured fields, a
768-dimension pgvector embedding, and deduplication metadata.

Deduplication Strategy
----------------------
Each listing is assigned a **canonical_hash** computed as::

    SHA-256( normalized_source_url  + "||" + lower(title) + "||" + lower(company) )

Before inserting a new row we check for an existing ``canonical_hash``.

*  If found → we only update ``scraped_at`` (proves the listing is still live)
   and skip the full extraction + embedding pipeline.
*  If not found → the listing is new; we run extraction, embedding, and insert.

``source_url`` also carries a unique index as a secondary guard so that the
same URL can never appear twice regardless of hash collisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class JobListing(Base):
    __tablename__ = "job_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Source metadata ──────────────────────────────────────────────────
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(
        String(2048), unique=True, index=True, nullable=False
    )
    canonical_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False,
        comment="SHA-256(url||title||company) for deduplication",
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── LLM-extracted structured fields ──────────────────────────────────
    title: Mapped[str | None] = mapped_column(String(512))
    company: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256))
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    stipend: Mapped[str | None] = mapped_column(String(256))
    required_skills: Mapped[dict | list | None] = mapped_column(JSONB)
    experience_level: Mapped[str | None] = mapped_column(String(64))
    deadline: Mapped[str | None] = mapped_column(String(128))

    # ── Embedding (768-dim for text-embedding-004) ───────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    # ── Timestamps ───────────────────────────────────────────────────────
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Extra indexes ────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_job_listings_source_name", "source_name"),
        Index(
            "ix_job_listings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_job_listings_tsv",
            text(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(company, '') || ' ' || coalesce(raw_text, ''))"
            ),
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<JobListing {self.title!r} @ {self.company!r}>"
