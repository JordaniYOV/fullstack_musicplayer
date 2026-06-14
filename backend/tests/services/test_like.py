"""
Tests for LikeService.

Requires sample_tracks fixture from conftest and a real async DB session.
Artists and Albums are created inline since conftest doesn't have fixtures for them.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.services.like import LikeService
from app.models.users import User, UserCreate
from app.models.artists import Artist
from app.models.albums import Album, AlbumsCover
from app.models.tracks import Track

pytestmark = pytest.mark.asyncio


# Fixtures 

@pytest_asyncio.fixture
async def user(async_session) -> User:
    u = User(
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        liked_songs=[],
        albums=[],
    )
    async_session.add(u)
    await async_session.commit()
    await async_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def artist(async_session) -> Artist:
    a = Artist(
        name="Test Artist",
        photo=b"img",
        image_type="image/jpeg",
        verified=False,
        monthly_listeners=0,
        plays=0,
        followers=0,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def album(async_session, artist) -> Album:
    cover = AlbumsCover(album_cover=b"cover", cover_type="image/jpeg")
    async_session.add(cover)
    await async_session.flush()

    a = Album(
        album_name="Test Album",
        artist_name=artist.name,
        total_tracks=1,
        year_release=2024,
        artist_id=artist.id,
        cover_id=cover.id,
        play_count=0,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def svc(async_session) -> LikeService:
    return LikeService(async_session)


# like_track 

async def test_like_track_success(svc, user, sample_tracks, async_session):
    ok = await svc.like_track(user.id, sample_tracks[0].id)
    assert ok is True

    await async_session.refresh(user)
    assert str(sample_tracks[0].id) in (user.liked_songs or [])


async def test_like_track_increments_likes(svc, user, sample_tracks, async_session):
    track = sample_tracks[1]
    before = track.likes

    await svc.like_track(user.id, track.id)

    result = await async_session.execute(select(Track).where(Track.id == track.id))
    refreshed = result.scalar_one()
    assert refreshed.likes == before + 1


async def test_like_track_unknown_returns_false(svc, user):
    ok = await svc.like_track(user.id, uuid.uuid4())
    assert ok is False


async def test_like_track_duplicate_raises(svc, user, sample_tracks):
    await svc.like_track(user.id, sample_tracks[0].id)
    with pytest.raises(ValueError, match="already liked"):
        await svc.like_track(user.id, sample_tracks[0].id)


# unlike_track 

async def test_unlike_track_success(svc, user, sample_tracks, async_session):
    await svc.like_track(user.id, sample_tracks[0].id)
    ok = await svc.unlike_track(user.id, sample_tracks[0].id)
    assert ok is True

    await async_session.refresh(user)
    assert str(sample_tracks[0].id) not in (user.liked_songs or [])


async def test_unlike_track_decrements_likes(svc, user, sample_tracks, async_session):
    track = sample_tracks[2]
    await svc.like_track(user.id, track.id)

    result = await async_session.execute(select(Track).where(Track.id == track.id))
    after_like = result.scalar_one().likes

    await svc.unlike_track(user.id, track.id)

    result2 = await async_session.execute(select(Track).where(Track.id == track.id))
    after_unlike = result2.scalar_one().likes
    assert after_unlike == after_like - 1


async def test_unlike_track_not_liked_raises(svc, user, sample_tracks):
    with pytest.raises(ValueError, match="not in liked songs"):
        await svc.unlike_track(user.id, sample_tracks[0].id)


async def test_unlike_track_unknown_returns_false(svc, user):
    ok = await svc.unlike_track(user.id, uuid.uuid4())
    assert ok is False


# get_liked_tracks 

async def test_get_liked_tracks_returns_in_order(svc, user, sample_tracks):
    for track in sample_tracks[:3]:
        await svc.like_track(user.id, track.id)

    liked = await svc.get_liked_tracks(user.id)
    assert len(liked) == 3
    assert liked[0].id == sample_tracks[0].id


async def test_get_liked_tracks_empty_returns_empty(svc, user):
    result = await svc.get_liked_tracks(user.id)
    assert result == []


async def test_get_liked_tracks_pagination(svc, user, sample_tracks):
    for track in sample_tracks:
        await svc.like_track(user.id, track.id)

    page1 = await svc.get_liked_tracks(user.id, limit=3, offset=0)
    page2 = await svc.get_liked_tracks(user.id, limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 2


# is_track_liked 

async def test_is_track_liked_true_after_like(svc, user, sample_tracks):
    await svc.like_track(user.id, sample_tracks[0].id)
    assert await svc.is_track_liked(user.id, sample_tracks[0].id) is True


async def test_is_track_liked_false_before_like(svc, user, sample_tracks):
    assert await svc.is_track_liked(user.id, sample_tracks[0].id) is False


async def test_is_track_liked_false_after_unlike(svc, user, sample_tracks):
    await svc.like_track(user.id, sample_tracks[0].id)
    await svc.unlike_track(user.id, sample_tracks[0].id)
    assert await svc.is_track_liked(user.id, sample_tracks[0].id) is False


# like_album / unlike_album

async def test_like_album_success(svc, user, album, async_session):
    ok = await svc.like_album(user.id, album.id)
    assert ok is True

    await async_session.refresh(user)
    assert str(album.id) in (user.albums or [])


async def test_like_album_duplicate_raises(svc, user, album):
    await svc.like_album(user.id, album.id)
    with pytest.raises(ValueError, match="already saved"):
        await svc.like_album(user.id, album.id)


async def test_unlike_album_success(svc, user, album, async_session):
    await svc.like_album(user.id, album.id)
    ok = await svc.unlike_album(user.id, album.id)
    assert ok is True

    await async_session.refresh(user)
    assert str(album.id) not in (user.albums or [])


async def test_unlike_album_not_saved_raises(svc, user, album):
    with pytest.raises(ValueError, match="not in saved albums"):
        await svc.unlike_album(user.id, album.id)


async def test_like_album_unknown_returns_false(svc, user):
    ok = await svc.like_album(user.id, uuid.uuid4())
    assert ok is False


async def test_get_liked_albums_returns_list(svc, user, album):
    await svc.like_album(user.id, album.id)
    albums = await svc.get_liked_albums(user.id)
    assert len(albums) == 1
    assert albums[0].id == album.id


# follow_artist / unfollow_artist 

async def test_follow_artist_increments_followers(svc, user, artist, async_session):
    before = artist.followers or 0
    ok = await svc.follow_artist(user.id, artist.id)
    assert ok is True

    result = await async_session.execute(select(Artist).where(Artist.id == artist.id))
    refreshed = result.scalar_one()
    assert refreshed.followers == before + 1


async def test_follow_artist_unknown_returns_false(svc, user):
    ok = await svc.follow_artist(user.id, uuid.uuid4())
    assert ok is False


async def test_unfollow_artist_decrements_followers(svc, user, artist, async_session):
    await svc.follow_artist(user.id, artist.id)

    result = await async_session.execute(select(Artist).where(Artist.id == artist.id))
    after_follow = result.scalar_one().followers
    print(after_follow)
    await svc.unfollow_artist(user.id, artist.id)

    result2 = await async_session.execute(select(Artist).where(Artist.id == artist.id))
    after_unfollow = result2.scalar_one().followers
    print(after_unfollow)
    assert after_unfollow == after_follow - 1


async def test_unfollow_artist_followers_never_goes_below_zero(svc, user, artist, async_session):
    # Artist has 0 followers — unfollow should clamp at 0
    ok = await svc.unfollow_artist(user.id, artist.id)
    assert ok is True

    result = await async_session.execute(select(Artist).where(Artist.id == artist.id))
    refreshed = result.scalar_one()
    assert (refreshed.followers or 0) >= 0


async def test_unfollow_artist_unknown_returns_false(svc, user):
    ok = await svc.unfollow_artist(user.id, uuid.uuid4())
    assert ok is False