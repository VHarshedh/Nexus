"""add_user_is_verified

Revision ID: c1e3f89a42d1
Revises: b9c25455568c
Create Date: 2026-09-13 15:03:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1e3f89a42d1'
down_revision: Union[str, None] = 'b9c25455568c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column with server_default=true initially to backfill existing users
    op.add_column(
        'users',
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    # Alter the default to false for all newly registered users
    op.alter_column('users', 'is_verified', server_default=sa.text('false'))


def downgrade() -> None:
    op.drop_column('users', 'is_verified')
