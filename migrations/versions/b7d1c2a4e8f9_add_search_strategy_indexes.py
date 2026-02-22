"""add search strategy indexes (trigram + fts)

Revision ID: b7d1c2a4e8f9
Revises: 9c4f6e1a2b7d
Create Date: 2026-02-17 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d1c2a4e8f9"
down_revision: Union[str, Sequence[str], None] = "9c4f6e1a2b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_news_articles_search_trgm
        ON news_articles
        USING gin (
          ((
            COALESCE(title, '') ||
            ' ' ||
            COALESCE(summary, '') ||
            ' ' ||
            COALESCE(content, '')
          )) gin_trgm_ops
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_news_articles_search_fts
        ON news_articles
        USING gin (
          to_tsvector(
            'simple',
            (
              COALESCE(title, '') ||
              ' ' ||
              COALESCE(summary, '') ||
              ' ' ||
              COALESCE(content, '')
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_news_articles_source_published_id
        ON news_articles (source, published_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_news_articles_published_id
        ON news_articles (published_at DESC, id DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_minutes_search_trgm
        ON council_minutes
        USING gin (
          ((
            COALESCE(council, '') ||
            ' ' ||
            COALESCE(committee, '') ||
            ' ' ||
            COALESCE("session", '') ||
            ' ' ||
            COALESCE(content, '') ||
            ' ' ||
            COALESCE(tag::text, '') ||
            ' ' ||
            COALESCE(attendee::text, '') ||
            ' ' ||
            COALESCE(agenda::text, '')
          )) gin_trgm_ops
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_minutes_search_fts
        ON council_minutes
        USING gin (
          to_tsvector(
            'simple',
            (
              COALESCE(council, '') ||
              ' ' ||
              COALESCE(committee, '') ||
              ' ' ||
              COALESCE("session", '') ||
              ' ' ||
              COALESCE(content, '') ||
              ' ' ||
              COALESCE(tag::text, '') ||
              ' ' ||
              COALESCE(attendee::text, '') ||
              ' ' ||
              COALESCE(agenda::text, '')
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_minutes_filters_date_id
        ON council_minutes (council, committee, "session", meeting_date DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_minutes_date_id
        ON council_minutes (meeting_date DESC, id DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_segments_search_trgm
        ON council_speech_segments
        USING gin (
          ((
            COALESCE(council, '') ||
            ' ' ||
            COALESCE(committee, '') ||
            ' ' ||
            COALESCE("session", '') ||
            ' ' ||
            COALESCE(content, '') ||
            ' ' ||
            COALESCE(summary, '') ||
            ' ' ||
            COALESCE(subject, '') ||
            ' ' ||
            COALESCE(party, '') ||
            ' ' ||
            COALESCE(constituency, '') ||
            ' ' ||
            COALESCE(department, '') ||
            ' ' ||
            COALESCE(tag::text, '') ||
            ' ' ||
            COALESCE(questioner::text, '') ||
            ' ' ||
            COALESCE(answerer::text, '')
          )) gin_trgm_ops
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_segments_search_fts
        ON council_speech_segments
        USING gin (
          to_tsvector(
            'simple',
            (
              COALESCE(council, '') ||
              ' ' ||
              COALESCE(committee, '') ||
              ' ' ||
              COALESCE("session", '') ||
              ' ' ||
              COALESCE(content, '') ||
              ' ' ||
              COALESCE(summary, '') ||
              ' ' ||
              COALESCE(subject, '') ||
              ' ' ||
              COALESCE(party, '') ||
              ' ' ||
              COALESCE(constituency, '') ||
              ' ' ||
              COALESCE(department, '') ||
              ' ' ||
              COALESCE(tag::text, '') ||
              ' ' ||
              COALESCE(questioner::text, '') ||
              ' ' ||
              COALESCE(answerer::text, '')
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_segments_filters_date_id
        ON council_speech_segments (
          council,
          committee,
          "session",
          importance,
          party,
          constituency,
          department,
          meeting_date DESC,
          id DESC
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_council_segments_date_id
        ON council_speech_segments (meeting_date DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_council_segments_date_id")
    op.execute("DROP INDEX IF EXISTS ix_council_segments_filters_date_id")
    op.execute("DROP INDEX IF EXISTS ix_council_segments_search_fts")
    op.execute("DROP INDEX IF EXISTS ix_council_segments_search_trgm")

    op.execute("DROP INDEX IF EXISTS ix_council_minutes_date_id")
    op.execute("DROP INDEX IF EXISTS ix_council_minutes_filters_date_id")
    op.execute("DROP INDEX IF EXISTS ix_council_minutes_search_fts")
    op.execute("DROP INDEX IF EXISTS ix_council_minutes_search_trgm")

    op.execute("DROP INDEX IF EXISTS ix_news_articles_published_id")
    op.execute("DROP INDEX IF EXISTS ix_news_articles_source_published_id")
    op.execute("DROP INDEX IF EXISTS ix_news_articles_search_fts")
    op.execute("DROP INDEX IF EXISTS ix_news_articles_search_trgm")
