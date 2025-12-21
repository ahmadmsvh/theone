"""increase_refresh_token_length

Revision ID: 9c0ee2006356
Revises: 25eb0c44d0ac
Create Date: 2025-12-20 19:00:10.112804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0ee2006356'
down_revision: Union[str, Sequence[str], None] = '25eb0c44d0ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change token column from String(255) to Text to support longer JWT tokens
    op.alter_column('refresh_tokens', 'token',
                    existing_type=sa.String(length=255),
                    type_=sa.Text(),
                    existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert token column back to String(255)
    op.alter_column('refresh_tokens', 'token',
                    existing_type=sa.Text(),
                    type_=sa.String(length=255),
                    existing_nullable=False)
