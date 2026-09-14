"""baseline_schema

Revision ID: b9c25455568c
Revises: 
Create Date: 2026-09-13 12:18:02.111649
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'b9c25455568c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. job_listings
    op.create_table(
        'job_listings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_name', sa.String(length=64), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=False),
        sa.Column('canonical_hash', sa.String(length=64), nullable=False, comment="SHA-256(url||title||company) for deduplication"),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('company', sa.String(length=256), nullable=True),
        sa.Column('location', sa.String(length=256), nullable=True),
        sa.Column('remote_ok', sa.Boolean(), default=False, nullable=False),
        sa.Column('stipend', sa.String(length=256), nullable=True),
        sa.Column('required_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('experience_level', sa.String(length=64), nullable=True),
        sa.Column('deadline', sa.String(length=128), nullable=True),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_job_listings_source_url', 'job_listings', ['source_url'], unique=True)
    op.create_index('ix_job_listings_canonical_hash', 'job_listings', ['canonical_hash'], unique=False)
    op.create_index('ix_job_listings_source_name', 'job_listings', ['source_name'], unique=False)
    op.create_index(
        'ix_job_listings_embedding_hnsw',
        'job_listings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.create_index(
        'ix_job_listings_tsv',
        'job_listings',
        [sa.literal_column("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(company, '') || ' ' || coalesce(raw_text, ''))")],
        unique=False,
        postgresql_using='gin',
    )

    # 3. resumes
    op.create_table(
        'resumes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('file_path', sa.String(length=1024), nullable=True),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 4. user_listing_matches
    op.create_table(
        'user_listing_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('job_listings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('saved', sa.Boolean(), default=False, nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default="pending", comment="pending | reviewed | applied | rejected"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. briefing_jobs
    op.create_table(
        'briefing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default="queued", comment="queued | generating_script | synthesizing_media | done | failed"),
        sa.Column('script', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(length=2048), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('briefing_jobs')
    op.drop_table('user_listing_matches')
    op.drop_table('resumes')
    op.drop_table('job_listings')
    op.drop_table('users')
