"""add segments dedupe hash

Revision ID: 0df9d6f13c5a
Revises: 35f43b134803
Create Date: 2026-02-17 19:12:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0df9d6f13c5a"
down_revision: Union[str, Sequence[str], None] = "35f43b134803"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("council_speech_segments", sa.Column("dedupe_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "ux_council_segments_dedupe_hash",
        "council_speech_segments",
        ["dedupe_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_council_segments_dedupe_hash", table_name="council_speech_segments")
    op.drop_column("council_speech_segments", "dedupe_hash")
