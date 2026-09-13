"""add_change_detection_columns

Revision ID: d2f4e8b1a3c5
Revises: c1e3f89a42d1
Create Date: 2026-09-13 16:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd2f4e8b1a3c5'
down_revision: Union[str, None] = 'c1e3f89a42d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'job_listings',
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.add_column(
        'job_listings',
        sa.Column('taken_down_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'user_listing_matches',
        sa.Column('change_alert', sa.Text(), nullable=True),
    )
    op.add_column(
        'user_listing_matches',
        sa.Column('change_alert_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_listing_matches', 'change_alert_at')
    op.drop_column('user_listing_matches', 'change_alert')
    op.drop_column('job_listings', 'taken_down_at')
    op.drop_column('job_listings', 'is_active')
