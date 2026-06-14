"""
Tests for SearchService.

Uses the real async DB with sample_tracks from conftest.
Artists and Albums created inline for album/artist search tests.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.search import SearchService, ENTITY_TRACK, ENTITY_ALBUM, ENTITY_ARTIST
from app.models.artists import Artist
from app.models.albums import Album, AlbumsCover

pytestmark = pytest.mark.asyncio


# Fixtures 

@pytest_asyncio.fixture
async def svc(async_session) -> SearchService:
    return SearchService(async_session)


@pytest_asyncio.fixture
async def artist_fixture(async_session) -> Artist:
    a = Artist(
        name="Queen",
        photo=b"img",
        image_type="image/jpeg",
        verified=True,
        monthly_listeners=50_000_000,
        followers=10_000_000,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def album_fixture(async_session, artist_fixture) -> Album:
    cover = AlbumsCover(album_cover=b"cover", cover_type="image/jpeg")
    async_session.add(cover)
    await async_session.flush()

    a = Album(
        album_name="A Night at the Opera",
        artist_name="Queen",
        total_tracks=12,
        year_release=1975,
        artist_id=artist_fixture.id,
        cover_id=cover.id,
        play_count=999_999,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


# Track search 
async def test_search_tracks_by_title(svc, sample_tracks):
    """'Bohemian' matches 'Bohemian Rhapsody'."""
    result = await svc.search("Bohemian", types={ENTITY_TRACK})
    assert result.total_tracks >= 1
    titles = [t.title for t in result.tracks]
    assert any("Bohemian" in t for t in titles)


async def test_search_tracks_by_artist(svc, sample_tracks):
    """Searching 'Queen' matches the artist field."""
    result = await svc.search("Queen", types={ENTITY_TRACK})
    assert result.total_tracks >= 1
    assert all(t.artist == "Queen" for t in result.tracks)


async def test_search_tracks_by_genre(svc, sample_tracks):
    result = await svc.search("Rock", types={ENTITY_TRACK})
    assert result.total_tracks >= 1
    assert all(t.genre == "Rock" for t in result.tracks)


async def test_search_tracks_case_insensitive(svc, sample_tracks):
    result = await svc.search("bohemian", types={ENTITY_TRACK})
    assert result.total_tracks >= 1


async def test_search_tracks_partial_match(svc, sample_tracks):
    result = await svc.search("Rhap", types={ENTITY_TRACK})
    assert result.total_tracks >= 1


async def test_search_tracks_no_match_returns_empty(svc, sample_tracks):
    result = await svc.search("xyzxyzxyznotatrack", types={ENTITY_TRACK})
    assert result.total_tracks == 0
    assert result.tracks == []


async def test_search_tracks_result_shape(svc, sample_tracks):
    """Result objects have all required fields."""
    result = await svc.search("Queen", types={ENTITY_TRACK})
    assert len(result.tracks) > 0
    t = result.tracks[0]
    assert t.id is not None
    assert t.title
    assert t.artist
    assert t.duration_sec > 0
    assert t.genre


async def test_search_tracks_sorted_by_plays(svc, sample_tracks, async_session):
    """Results are ranked by all_time_plays descending."""
    from sqlalchemy import update
    from app.models.tracks import Track

    # Give Bohemian Rhapsody the most plays
    await async_session.execute(
        update(Track).where(Track.title == "Bohemian Rhapsody").values(all_time_plays=9999)
    )
    await async_session.execute(
        update(Track).where(Track.title == "Hotel California").values(all_time_plays=1)
    )
    await async_session.commit()

    result = await svc.search("Rock", types={ENTITY_TRACK})
    plays = [t.all_time_plays for t in result.tracks]
    assert plays == sorted(plays, reverse=True)


# Album search 
async def test_search_albums_by_name(svc, album_fixture):
    result = await svc.search("Opera", types={ENTITY_ALBUM})
    assert result.total_albums >= 1
    names = [a.album_name for a in result.albums]
    assert any("Opera" in n for n in names)


async def test_search_albums_by_artist(svc, album_fixture):
    result = await svc.search("Queen", types={ENTITY_ALBUM})
    assert result.total_albums >= 1


async def test_search_albums_no_match(svc):
    result = await svc.search("zzznomatchalbum", types={ENTITY_ALBUM})
    assert result.total_albums == 0


async def test_search_albums_result_shape(svc, album_fixture):
    result = await svc.search("Queen", types={ENTITY_ALBUM})
    assert len(result.albums) > 0
    a = result.albums[0]
    assert a.id is not None
    assert a.album_name
    assert a.year_release > 0


# Artist search 

async def test_search_artists_by_name(svc, artist_fixture):
    result = await svc.search("Queen", types={ENTITY_ARTIST})
    assert result.total_artists >= 1
    names = [a.name for a in result.artists]
    assert "Queen" in names


async def test_search_artists_no_match(svc):
    result = await svc.search("zzznomatchartist", types={ENTITY_ARTIST})
    assert result.total_artists == 0


async def test_search_artists_result_shape(svc, artist_fixture):
    result = await svc.search("Queen", types={ENTITY_ARTIST})
    a = result.artists[0]
    assert a.id is not None
    assert a.name
    assert isinstance(a.verified, bool)

# Unified search (all types) 

async def test_search_all_types_returns_all_buckets(svc, sample_tracks, album_fixture, artist_fixture):
    result = await svc.search("Queen")
    # tracks has "Bohemian Rhapsody" by Queen; albums has "A Night at the Opera" by Queen; artist is Queen
    assert isinstance(result.tracks, list)
    assert isinstance(result.albums, list)
    assert isinstance(result.artists, list)


async def test_search_response_has_query_field(svc, sample_tracks):
    result = await svc.search("imagine")
    assert result.query == "imagine"


# Type filtering

async def test_search_only_tracks_returns_no_albums_or_artists(svc, sample_tracks, album_fixture):
    result = await svc.search("Queen", types={ENTITY_TRACK})
    assert result.albums == []
    assert result.artists == []


async def test_search_only_albums_returns_no_tracks_or_artists(svc, album_fixture):
    result = await svc.search("Queen", types={ENTITY_ALBUM})
    assert result.tracks == []
    assert result.artists == []


async def test_search_tracks_and_artists_no_albums(svc, sample_tracks, artist_fixture):
    result = await svc.search("Queen", types={ENTITY_TRACK, ENTITY_ARTIST})
    assert result.albums == []


# Limit

async def test_search_limit_applied(svc, sample_tracks):
    result = await svc.search("", types={ENTITY_TRACK}, limit=2)
    # empty query returns empty (service guards against it)
    assert result.tracks == []


async def test_search_limit_restricts_tracks(svc, sample_tracks):
    result = await svc.search("a", types={ENTITY_TRACK}, limit=2)
    assert len(result.tracks) <= 2


# Empty / whitespace query

async def test_search_empty_query_returns_empty(svc):
    result = await svc.search("")
    assert result.tracks == []
    assert result.albums == []
    assert result.artists == []


async def test_search_whitespace_query_returns_empty(svc):
    result = await svc.search("   ")
    assert result.tracks == []


# DB error resilience 

async def test_search_tracks_db_error_returns_empty(async_session):
    """A DB error in track search returns [] instead of crashing."""
    svc = SearchService(async_session)
    with patch.object(async_session, "execute", side_effect=Exception("db down")):
        result = await svc.search("queen", types={ENTITY_TRACK})
    assert result.tracks == []


async def test_search_albums_db_error_returns_empty(async_session):
    svc = SearchService(async_session)
    with patch.object(async_session, "execute", side_effect=Exception("db down")):
        result = await svc.search("queen", types={ENTITY_ALBUM})
    assert result.albums == []


async def test_search_artists_db_error_returns_empty(async_session):
    svc = SearchService(async_session)
    with patch.object(async_session, "execute", side_effect=Exception("db down")):
        result = await svc.search("queen", types={ENTITY_ARTIST})
    assert result.artists == []