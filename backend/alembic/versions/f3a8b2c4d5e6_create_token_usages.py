"""Create token_usages table

Revision ID: f3a8b2c4d5e6
Revises: ed0edbd50a47
Create Date: 2026-09-13 18:46:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a8b2c4d5e6'
down_revision: Union[str, None] = 'ed0edbd50a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'token_usages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('feature', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_inr', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_token_usages_user_id'), 'token_usages', ['user_id'], unique=False)
    op.create_index(op.f('ix_token_usages_feature'), 'token_usages', ['feature'], unique=False)
    op.create_index(op.f('ix_token_usages_created_at'), 'token_usages', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_token_usages_created_at'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_feature'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_user_id'), table_name='token_usages')
    op.drop_table('token_usages')
