"""
Integration tests for library routes.

POST   /me/tracks/{id}/like
DELETE /me/tracks/{id}/like
GET    /me/tracks/liked
GET    /me/tracks/{id}/liked
POST   /me/albums/{id}/save
DELETE /me/albums/{id}/save
GET    /me/albums/saved
POST   /me/artists/{id}/follow
DELETE /me/artists/{id}/follow
"""
from __future__ import annotations

import uuid


import pytest_asyncio

from app.models.artists import Artist
from app.models.albums import Album, AlbumsCover


#Helpers
async def _register_and_login(async_client) -> str:
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    email = f"lib_{suffix}@example.com"
    password = "Str0ngPass!"
    await async_client.post(
        "/user/signup",
        json={"email": email, "password": password, "full_name": "Lib User"},
    )
    resp = await async_client.post(
        "/login/access-token",
        data={"username": email, "password": password},
    )
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def token(async_client) -> str:
    return await _register_and_login(async_client)


@pytest_asyncio.fixture
async def db_artist(async_session) -> Artist:
    a = Artist(
        name=f"Artist_{uuid.uuid4().hex[:6]}",
        photo=b"img",
        image_type="image/jpeg",
        verified=False,
        monthly_listeners=0,
        followers=100,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


@pytest_asyncio.fixture
async def db_album(async_session, db_artist) -> Album:
    cover = AlbumsCover(album_cover=b"cover", cover_type="image/jpeg")
    async_session.add(cover)
    await async_session.flush()
    a = Album(
        album_name=f"Album_{uuid.uuid4().hex[:6]}",
        artist_name=db_artist.name,
        total_tracks=5,
        year_release=2023,
        artist_id=db_artist.id,
        cover_id=cover.id,
        play_count=0,
    )
    async_session.add(a)
    await async_session.commit()
    await async_session.refresh(a)
    return a


# Auth guards 

async def test_like_track_requires_auth(async_client, sample_tracks):
    resp = await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like")
    assert resp.status_code == 401


async def test_unlike_track_requires_auth(async_client, sample_tracks):
    resp = await async_client.delete(f"/me/tracks/{sample_tracks[0].id}/like")
    assert resp.status_code == 401


async def test_get_liked_tracks_requires_auth(async_client):
    resp = await async_client.get("/me/tracks/liked")
    assert resp.status_code == 401


async def test_follow_artist_requires_auth(async_client, db_artist):
    resp = await async_client.post(f"/me/artists/{db_artist.id}/follow")
    assert resp.status_code == 401


# Like track

async def test_like_track_success(async_client, token, sample_tracks):
    resp = await async_client.post(
        f"/me/tracks/{sample_tracks[0].id}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "liked" in resp.json()["message"].lower()


async def test_like_track_unknown_returns_404(async_client, token):
    resp = await async_client.post(
        f"/me/tracks/{uuid.uuid4()}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_like_track_duplicate_returns_409(async_client, token, sample_tracks):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    resp = await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    assert resp.status_code == 409


# Unlike track

async def test_unlike_track_success(async_client, token, sample_tracks):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    resp = await async_client.delete(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    assert resp.status_code == 200


async def test_unlike_track_not_liked_returns_400(async_client, token, sample_tracks):
    resp = await async_client.delete(
        f"/me/tracks/{sample_tracks[0].id}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_unlike_track_unknown_returns_404(async_client, token):
    resp = await async_client.delete(
        f"/me/tracks/{uuid.uuid4()}/like",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# Get liked tracks 

async def test_get_liked_tracks_returns_list(async_client, token):
    resp = await async_client.get(
        "/me/tracks/liked",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_liked_tracks_contains_liked(async_client, token, sample_tracks):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    await async_client.post(f"/me/tracks/{sample_tracks[1].id}/like", headers=headers)

    resp = await async_client.get("/me/tracks/liked", headers=headers)
    ids = [t["id"] for t in resp.json()]
    assert str(sample_tracks[0].id) in ids
    assert str(sample_tracks[1].id) in ids


async def test_get_liked_tracks_not_in_list_after_unlike(async_client, token, sample_tracks):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)
    await async_client.delete(f"/me/tracks/{sample_tracks[0].id}/like", headers=headers)

    resp = await async_client.get("/me/tracks/liked", headers=headers)
    ids = [t["id"] for t in resp.json()]
    assert str(sample_tracks[0].id) not in ids


# Is track liked 

async def test_is_track_liked_false_before_like(async_client, token, sample_tracks):
    resp = await async_client.get(
        f"/me/tracks/{sample_tracks[2].id}/liked",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["liked"] is False


async def test_is_track_liked_true_after_like(async_client, token, sample_tracks):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/tracks/{sample_tracks[2].id}/like", headers=headers)
    resp = await async_client.get(f"/me/tracks/{sample_tracks[2].id}/liked", headers=headers)
    assert resp.json()["liked"] is True


# Save album 

async def test_save_album_success(async_client, token, db_album):
    resp = await async_client.post(
        f"/me/albums/{db_album.id}/save",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_save_album_unknown_returns_404(async_client, token):
    resp = await async_client.post(
        f"/me/albums/{uuid.uuid4()}/save",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_save_album_duplicate_returns_409(async_client, token, db_album):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/albums/{db_album.id}/save", headers=headers)
    resp = await async_client.post(f"/me/albums/{db_album.id}/save", headers=headers)
    assert resp.status_code == 409


async def test_unsave_album_success(async_client, token, db_album):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/albums/{db_album.id}/save", headers=headers)
    resp = await async_client.delete(f"/me/albums/{db_album.id}/save", headers=headers)
    assert resp.status_code == 200


async def test_unsave_album_not_saved_returns_400(async_client, token, db_album):
    resp = await async_client.delete(
        f"/me/albums/{db_album.id}/save",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_get_saved_albums_contains_saved(async_client, token, db_album):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/albums/{db_album.id}/save", headers=headers)
    resp = await async_client.get("/me/albums/saved", headers=headers)
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert str(db_album.id) in ids


# Follow artist 

async def test_follow_artist_success(async_client, token, db_artist):
    resp = await async_client.post(
        f"/me/artists/{db_artist.id}/follow",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "following" in resp.json()["message"].lower()


async def test_follow_artist_unknown_returns_404(async_client, token):
    resp = await async_client.post(
        f"/me/artists/{uuid.uuid4()}/follow",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_unfollow_artist_success(async_client, token, db_artist):
    headers = {"Authorization": f"Bearer {token}"}
    await async_client.post(f"/me/artists/{db_artist.id}/follow", headers=headers)
    resp = await async_client.delete(f"/me/artists/{db_artist.id}/follow", headers=headers)
    assert resp.status_code == 200


async def test_unfollow_artist_unknown_returns_404(async_client, token):
    resp = await async_client.delete(
        f"/me/artists/{uuid.uuid4()}/follow",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_follow_increments_followers(async_client, token, db_artist, async_session):
    from sqlalchemy import select
    from app.models.artists import Artist as ArtistModel

    result = await async_session.execute(
        select(ArtistModel).where(ArtistModel.id == db_artist.id)
    )
    before = result.scalar_one().followers or 0

    await async_client.post(
        f"/me/artists/{db_artist.id}/follow",
        headers={"Authorization": f"Bearer {token}"},
    )

    await async_session.refresh(db_artist)
    result2 = await async_session.execute(
        select(ArtistModel).where(ArtistModel.id == db_artist.id)
    )
    after = result2.scalar_one().followers or 0
    assert after == before + 1