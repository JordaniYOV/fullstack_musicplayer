"""add pg_trgm indexes for search

Revision ID: 2f458f0ee761
Revises: 51137bc2e330
Create Date: 2026-06-13 22:43:51.776403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f458f0ee761'
down_revision: Union[str, Sequence[str], None] = '51137bc2e330'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable the trigram extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
 
    # Track — search by title, artist, genre
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_title_trgm "
        "ON track USING GIN (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_artist_trgm "
        "ON track USING GIN (artist gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_genre_trgm "
        "ON track USING GIN (genre gin_trgm_ops)"
    )
 
    # Album — search by name, artist name
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_name_trgm "
        "ON album USING GIN (album_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_artist_trgm "
        "ON album USING GIN (artist_name gin_trgm_ops)"
    )
 
    # Artist — search by name, bio
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_name_trgm "
        "ON artist USING GIN (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_bio_trgm "
        "ON artist USING GIN (bio gin_trgm_ops)"
    )
 
 
def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_artist_bio_trgm")
    op.execute("DROP INDEX IF EXISTS idx_artist_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_album_artist_trgm")
    op.execute("DROP INDEX IF EXISTS idx_album_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_track_genre_trgm")
    op.execute("DROP INDEX IF EXISTS idx_track_artist_trgm")
    op.execute("DROP INDEX IF EXISTS idx_track_title_trgm")