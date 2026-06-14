"""
Integration tests for GET /search.

No auth required — search is public.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.models.artists import Artist
from app.models.albums import Album, AlbumsCover


# Fixtures 

@pytest_asyncio.fixture
async def search_artist(async_session) -> Artist:
    a = Artist(
        name="Radiohead",
        photo=b"img",
        image_type="image/jpeg",
        verified=True,
        monthly_listeners=5_000_000,
        followers=3_000_000,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def search_album(async_session, search_artist) -> Album:
    cover = AlbumsCover(album_cover=b"cover", cover_type="image/jpeg")
    async_session.add(cover)
    await async_session.flush()
    a = Album(
        album_name="OK Computer",
        artist_name="Radiohead",
        total_tracks=12,
        year_release=1997,
        artist_id=search_artist.id,
        cover_id=cover.id,
        play_count=500_000,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


# Basic search 

async def test_search_requires_q_param(async_client):
    resp = await async_client.get("/search")
    assert resp.status_code == 422


async def test_search_empty_q_returns_422(async_client):
    resp = await async_client.get("/search?q=")
    assert resp.status_code == 422


async def test_search_returns_200(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Queen")
    assert resp.status_code == 200


async def test_search_response_shape(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Queen")
    body = resp.json()
    assert "query" in body
    assert "tracks" in body
    assert "albums" in body
    assert "artists" in body
    assert "total_tracks" in body
    assert "total_albums" in body
    assert "total_artists" in body


async def test_search_query_reflected_in_response(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Bohemian")
    assert resp.json()["query"] == "Bohemian"


# Track results

async def test_search_finds_track_by_title(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Bohemian&types=track")
    body = resp.json()
    titles = [t["title"] for t in body["tracks"]]
    assert any("Bohemian" in t for t in titles)


async def test_search_finds_track_by_artist(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Nirvana&types=track")
    body = resp.json()
    assert body["total_tracks"] >= 1
    assert all(t["artist"] == "Nirvana" for t in body["tracks"])


async def test_search_track_result_fields(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Queen&types=track")
    if resp.json()["total_tracks"] > 0:
        t = resp.json()["tracks"][0]
        assert "id" in t
        assert "title" in t
        assert "artist" in t
        assert "duration_sec" in t
        assert "genre" in t


# Album results 

async def test_search_finds_album_by_name(async_client, search_album):
    resp = await async_client.get("/search?q=OK+Computer&types=album")
    body = resp.json()
    assert body["total_albums"] >= 1
    names = [a["album_name"] for a in body["albums"]]
    assert any("OK Computer" in n for n in names)


async def test_search_album_result_fields(async_client, search_album):
    resp = await async_client.get("/search?q=Radiohead&types=album")
    if resp.json()["total_albums"] > 0:
        a = resp.json()["albums"][0]
        assert "id" in a
        assert "album_name" in a
        assert "artist_name" in a
        assert "year_release" in a


# Artist results

async def test_search_finds_artist_by_name(async_client, search_artist):
    resp = await async_client.get("/search?q=Radiohead&types=artist")
    body = resp.json()
    assert body["total_artists"] >= 1
    names = [a["name"] for a in body["artists"]]
    assert "Radiohead" in names


async def test_search_artist_result_fields(async_client, search_artist):
    resp = await async_client.get("/search?q=Radiohead&types=artist")
    if resp.json()["total_artists"] > 0:
        a = resp.json()["artists"][0]
        assert "id" in a
        assert "name" in a
        assert "verified" in a


# Type filtering 

async def test_search_type_track_only(async_client, sample_tracks):
    resp = await async_client.get("/search?q=Queen&types=track")
    body = resp.json()
    assert body["albums"] == []
    assert body["artists"] == []


async def test_search_type_album_only(async_client, search_album):
    resp = await async_client.get("/search?q=Radiohead&types=album")
    body = resp.json()
    assert body["tracks"] == []
    assert body["artists"] == []


async def test_search_type_artist_only(async_client, search_artist):
    resp = await async_client.get("/search?q=Radiohead&types=artist")
    body = resp.json()
    assert body["tracks"] == []
    assert body["albums"] == []


async def test_search_multiple_types(async_client, sample_tracks, search_artist):
    resp = await async_client.get("/search?q=Queen&types=track,artist")
    body = resp.json()
    assert body["albums"] == []
    # tracks and artists can both have results


async def test_search_invalid_type_returns_422(async_client):
    resp = await async_client.get("/search?q=test&types=invalid_type")
    assert resp.status_code == 422


# Limit 

async def test_search_limit_applied(async_client, sample_tracks):
    resp = await async_client.get("/search?q=a&types=track&limit=1")
    body = resp.json()
    assert len(body["tracks"]) <= 1


async def test_search_limit_default_is_10(async_client, sample_tracks):
    resp = await async_client.get("/search?q=a&types=track")
    body = resp.json()
    assert len(body["tracks"]) <= 10


async def test_search_limit_max_50(async_client):
    resp = await async_client.get("/search?q=a&limit=51")
    assert resp.status_code == 422


async def test_search_limit_min_1(async_client):
    resp = await async_client.get("/search?q=a&limit=0")
    assert resp.status_code == 422


# No results 

async def test_search_no_match_returns_empty_lists(async_client):
    resp = await async_client.get("/search?q=xyzxyzxyznotatrack")
    body = resp.json()
    assert body["tracks"] == []
    assert body["albums"] == []
    assert body["artists"] == []
    assert body["total_tracks"] == 0


# Case insensitivity 

async def test_search_case_insensitive(async_client, sample_tracks):
    lower = await async_client.get("/search?q=bohemian&types=track")
    upper = await async_client.get("/search?q=BOHEMIAN&types=track")
    assert lower.json()["total_tracks"] == upper.json()["total_tracks"]


# Long query 

async def test_search_query_too_long_returns_422(async_client):
    resp = await async_client.get(f"/search?q={'a' * 201}")
    assert resp.status_code == 422