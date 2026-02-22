"""make news published_at timestamptz

Revision ID: 9c4f6e1a2b7d
Revises: 0df9d6f13c5a
Create Date: 2026-02-17 23:58:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4f6e1a2b7d"
down_revision: Union[str, Sequence[str], None] = "0df9d6f13c5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "news_articles",
        "published_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="published_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "news_articles",
        "published_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="published_at AT TIME ZONE 'UTC'",
    )
