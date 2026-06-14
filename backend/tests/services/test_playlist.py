"""
Tests for PlaylistService.

Uses the real async DB session from conftest (test_charts Postgres).
All tests are isolated via session rollback after each test.
"""
from __future__ import annotations

from os import O_WRONLY
import uuid

import pytest
import pytest_asyncio

from app.core.services.playlist import PlaylistService
from app.models.playlists import PlaylistCreate, PlaylistUpdate
from app.models.users import User


pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────

# @pytest_asyncio.fixture
# async def owner_id(async_session) -> uuid.UUID:
    
#     await async_session.execute(

#     )


# @pytest_asyncio.fixture
# async def other_user_id() -> uuid.UUID:
#     return uuid.uuid4()


@pytest_asyncio.fixture
async def svc(async_session) -> PlaylistService:
    return PlaylistService(async_session)


@pytest_asyncio.fixture
async def public_playlist(svc, sample_users):
    owner_id = sample_users[0].id
    return await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="My Public List", is_public=True),
    )


@pytest_asyncio.fixture
async def private_playlist(svc, sample_users):
    owner_id = sample_users[0].id
    return await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="My Private List", is_public=False),
    )


# create 

async def test_create_returns_playlist(svc, sample_users):
    owner_id = sample_users[0].id
    pl = await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="Road Trip", is_public=True),
    )
    assert pl.id is not None
    assert pl.name == "Road Trip"
    assert pl.owner_id == owner_id
    assert pl.is_public is True


async def test_create_private_playlist(svc, sample_users):
    owner_id = sample_users[0].id
    pl = await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="Secret Mix", is_public=False),
    )
    assert pl.is_public is False


async def test_create_with_description(svc, sample_users):
    owner_id = sample_users[0].id
    pl = await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="Chill", description="For late nights", is_public=True),
    )
    assert pl.description == "For late nights"


async def test_create_assigns_unique_ids(svc, sample_users):
    owner_id = sample_users[0].id
    pl1 = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="A", is_public=True))
    pl2 = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="B", is_public=True))
    assert pl1.id != pl2.id


# get_by_id 

async def test_get_by_id_public_without_auth(svc, public_playlist):
    result = await svc.get_by_id(
        playlist_id=public_playlist.id,
        requesting_user_id=None,
    )
    assert result is not None
    assert result.id == public_playlist.id


async def test_get_by_id_private_by_owner(svc, private_playlist, sample_users):
    owner_id = sample_users[0].id
    result = await svc.get_by_id(
        playlist_id=private_playlist.id,
        requesting_user_id=owner_id,
    )
    assert result is not None


async def test_get_by_id_private_by_other_user_returns_none(svc, private_playlist, sample_users):
    other_user_id = sample_users[1].id
    result = await svc.get_by_id(
        playlist_id=private_playlist.id,
        requesting_user_id=other_user_id,
    )
    assert result is None


async def test_get_by_id_not_found_returns_none(svc):
    result = await svc.get_by_id(playlist_id=uuid.uuid4())
    assert result is None


async def test_get_by_id_includes_tracks(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="With Tracks", is_public=True),
    )
    await svc.add_track(pl.id, owner_id, sample_tracks[0].id)

    result = await svc.get_by_id(pl.id)
    assert result is not None
    assert len(result.tracks) == 1
    assert result.tracks[0].id == sample_tracks[0].id
    assert result.track_count == 1


# get_user_playlists 

async def test_get_user_playlists_returns_owned(svc, sample_users):
    owner_id = sample_users[0].id
    other_user_id = sample_users[1].id
    await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Mine", is_public=True))
    await svc.create(owner_id=other_user_id, data=PlaylistCreate(name="Theirs", is_public=True))

    mine = await svc.get_user_playlists(owner_id=owner_id)
    assert all(p.owner_id == owner_id for p in mine)


async def test_get_user_playlists_includes_private(svc, sample_users):
    owner_id = sample_users[0].id
    await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Public", is_public=True))
    await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Private", is_public=False))

    result = await svc.get_user_playlists(owner_id=owner_id)
    names = {p.name for p in result}
    assert "Public" in names
    assert "Private" in names


async def test_get_user_playlists_pagination(svc, sample_users):
    owner_id = sample_users[0].id
    for i in range(5):
        await svc.create(owner_id=owner_id, data=PlaylistCreate(name=f"PL{i}", is_public=True))

    page1 = await svc.get_user_playlists(owner_id=owner_id, limit=3, offset=0)
    page2 = await svc.get_user_playlists(owner_id=owner_id, limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 2
    ids1 = {p.id for p in page1}
    ids2 = {p.id for p in page2}
    assert ids1.isdisjoint(ids2)


# get_public_playlists 

async def test_get_public_playlists_excludes_private(svc, sample_users):
    owner_id = sample_users[0].id
    await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Pub", is_public=True))
    await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Priv", is_public=False))

    result = await svc.get_public_playlists()
    assert all(p.is_public for p in result)


# update 

async def test_update_changes_name(svc, public_playlist, sample_users):
    owner_id = sample_users[0].id
    updated = await svc.update(
        playlist_id=public_playlist.id,
        owner_id=owner_id,
        data=PlaylistUpdate(name="New Name", description=None),
    )
    assert updated is not None
    assert updated.name == "New Name"


async def test_update_by_non_owner_returns_none(svc, public_playlist, sample_users):
    other_user_id = sample_users[1].id
    result = await svc.update(
        playlist_id=public_playlist.id,
        owner_id=other_user_id,
        data=PlaylistUpdate(name="Hijacked", description=None),
    )
    assert result is None


async def test_update_not_found_returns_none(svc, sample_users):
    owner_id = sample_users[0].id
    result = await svc.update(
        playlist_id=uuid.uuid4(),
        owner_id=owner_id,
        data=PlaylistUpdate(name="Ghost", description=None),
    )
    assert result is None


# delete 

async def test_delete_removes_playlist(svc, sample_users):
    owner_id = sample_users[0].id
    pl = await svc.create(
        owner_id=owner_id,
        data=PlaylistCreate(name="Temp", is_public=True),
    )
    deleted = await svc.delete(pl.id, owner_id)
    assert deleted is True

    result = await svc.get_by_id(pl.id)
    assert result is None


async def test_delete_by_non_owner_returns_false(svc, public_playlist, sample_users):
    other_user_id = sample_users[1].id
    result = await svc.delete(public_playlist.id, other_user_id)
    assert result is False


async def test_delete_not_found_returns_false(svc, sample_users):
    owner_id = sample_users[0].id
    result = await svc.delete(uuid.uuid4(), owner_id)
    assert result is False


# add_track

async def test_add_track_success(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Test", is_public=True))
    ok = await svc.add_track(pl.id, owner_id, sample_tracks[0].id)
    assert ok is True

    full = await svc.get_by_id(pl.id)
    assert len(full.tracks) == 1


async def test_add_multiple_tracks(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Multi", is_public=True))
    for track in sample_tracks[:3]:
        await svc.add_track(pl.id, owner_id, track.id)

    full = await svc.get_by_id(pl.id)
    assert full.track_count == 3


async def test_add_track_duplicate_raises(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Dup", is_public=True))
    await svc.add_track(pl.id, owner_id, sample_tracks[0].id)

    with pytest.raises(ValueError, match="already in playlist"):
        await svc.add_track(pl.id, owner_id, sample_tracks[0].id)


async def test_add_track_unknown_track_returns_false(svc, sample_users):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="T", is_public=True))
    ok = await svc.add_track(pl.id, owner_id, uuid.uuid4())
    assert ok is False


async def test_add_track_to_other_users_playlist_returns_false(
    svc, public_playlist, sample_users, sample_tracks
):
    other_user_id = sample_users[1].id
    ok = await svc.add_track(public_playlist.id, other_user_id, sample_tracks[0].id)
    assert ok is False


# remove_track

async def test_remove_track_success(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Remove", is_public=True))
    await svc.add_track(pl.id, owner_id, sample_tracks[0].id)

    ok = await svc.remove_track(pl.id, owner_id, sample_tracks[0].id)
    assert ok is True

    full = await svc.get_by_id(pl.id)
    assert full.track_count == 0


async def test_remove_track_not_in_playlist_returns_false(svc, sample_users, sample_tracks):
    owner_id = sample_users[0].id
    pl = await svc.create(owner_id=owner_id, data=PlaylistCreate(name="Empty", is_public=True))
    ok = await svc.remove_track(pl.id, owner_id, sample_tracks[0].id)
    assert ok is False


async def test_remove_track_by_non_owner_returns_false(
    svc, public_playlist, sample_users, sample_tracks
):
    owner_id = sample_users[0].id
    other_user_id = sample_users[1].id
    await svc.add_track(public_playlist.id, owner_id, sample_tracks[0].id)
    ok = await svc.remove_track(public_playlist.id, other_user_id, sample_tracks[0].id)
    assert ok is False