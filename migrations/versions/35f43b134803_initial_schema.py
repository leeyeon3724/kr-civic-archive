"""initial schema

Revision ID: 35f43b134803
Revises:
Create Date: 2026-02-17 15:19:28.991188

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "35f43b134803"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "news_articles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "council_minutes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("council", sa.String(length=255), nullable=False),
        sa.Column("committee", sa.String(length=255), nullable=True),
        sa.Column("session", sa.String(length=255), nullable=True),
        sa.Column("meeting_no", sa.Integer(), nullable=True),
        sa.Column("meeting_no_combined", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("meeting_date", sa.Date(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tag", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attendee", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("agenda", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "council_speech_segments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("council", sa.String(length=255), nullable=False),
        sa.Column("committee", sa.String(length=255), nullable=True),
        sa.Column("session", sa.String(length=255), nullable=True),
        sa.Column("meeting_no", sa.Integer(), nullable=True),
        sa.Column("meeting_date", sa.Date(), nullable=True),
        sa.Column("meeting_no_combined", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("tag", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("importance", sa.SmallInteger(), nullable=True),
        sa.Column("moderator", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("questioner", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("answerer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("party", sa.String(length=255), nullable=True),
        sa.Column("constituency", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index("ix_news_articles_source", "news_articles", ["source"], unique=False)
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"], unique=False)

    op.create_index("ix_council_minutes_council", "council_minutes", ["council"], unique=False)
    op.create_index("ix_council_minutes_committee", "council_minutes", ["committee"], unique=False)
    op.create_index("ix_council_minutes_session", "council_minutes", ["session"], unique=False)
    op.create_index("ix_council_minutes_meeting_date", "council_minutes", ["meeting_date"], unique=False)
    op.create_index("ix_council_minutes_meeting_no_combined", "council_minutes", ["meeting_no_combined"], unique=False)

    op.create_index("ix_council_segments_council", "council_speech_segments", ["council"], unique=False)
    op.create_index("ix_council_segments_committee", "council_speech_segments", ["committee"], unique=False)
    op.create_index("ix_council_segments_session", "council_speech_segments", ["session"], unique=False)
    op.create_index("ix_council_segments_meeting_date", "council_speech_segments", ["meeting_date"], unique=False)
    op.create_index("ix_council_segments_importance", "council_speech_segments", ["importance"], unique=False)
    op.create_index("ix_council_segments_party", "council_speech_segments", ["party"], unique=False)
    op.create_index("ix_council_segments_constituency", "council_speech_segments", ["constituency"], unique=False)
    op.create_index("ix_council_segments_department", "council_speech_segments", ["department"], unique=False)
    op.create_index("ix_council_segments_meeting_no_combined", "council_speech_segments", ["meeting_no_combined"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_council_segments_meeting_no_combined", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_department", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_constituency", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_party", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_importance", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_meeting_date", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_session", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_committee", table_name="council_speech_segments")
    op.drop_index("ix_council_segments_council", table_name="council_speech_segments")

    op.drop_index("ix_council_minutes_meeting_no_combined", table_name="council_minutes")
    op.drop_index("ix_council_minutes_meeting_date", table_name="council_minutes")
    op.drop_index("ix_council_minutes_session", table_name="council_minutes")
    op.drop_index("ix_council_minutes_committee", table_name="council_minutes")
    op.drop_index("ix_council_minutes_council", table_name="council_minutes")

    op.drop_index("ix_news_articles_published_at", table_name="news_articles")
    op.drop_index("ix_news_articles_source", table_name="news_articles")

    op.drop_table("council_speech_segments")
    op.drop_table("council_minutes")
    op.drop_table("news_articles")
