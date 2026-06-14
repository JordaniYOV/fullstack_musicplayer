"""
Integration tests for playlist routes.

POST   /playlists
GET    /playlists
GET    /playlists/public
GET    /playlists/{id}
PATCH  /playlists/{id}
DELETE /playlists/{id}
POST   /playlists/{id}/tracks
DELETE /playlists/{id}/tracks/{track_id}
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio


# Helpers

async def _register_and_login(async_client) -> str:
    import random, string
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    email = f"pl_{suffix}@example.com"
    password = "Str0ngPass!"

    await async_client.post(
        "/user/signup",
        json={"email": email, "password": password, "full_name": "PL User"},
    )
    token_resp = await async_client.post(
        "/login/access-token",
        data={"username": email, "password": password},
    )
    return token_resp.json()["access_token"]


async def _create_playlist(async_client, token: str, name: str = "My List", public: bool = True) -> dict:
    resp = await async_client.post(
        "/playlists",
        json={"name": name, "is_public": public, "description": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# Auth guards

async def test_create_playlist_requires_auth(async_client):
    resp = await async_client.post(
        "/playlists",
        json={"name": "Test", "is_public": True},
    )
    assert resp.status_code == 401


async def test_list_my_playlists_requires_auth(async_client):
    resp = await async_client.get("/playlists")
    assert resp.status_code == 401


async def test_update_playlist_requires_auth(async_client):
    resp = await async_client.patch(
        f"/playlists/{uuid.uuid4()}",
        json={"name": "X", "description": None},
    )
    assert resp.status_code == 401


async def test_delete_playlist_requires_auth(async_client):
    resp = await async_client.delete(f"/playlists/{uuid.uuid4()}")
    assert resp.status_code == 401


# Create 

async def test_create_playlist_returns_201(async_client):
    token = await _register_and_login(async_client)
    resp = await async_client.post(
        "/playlists",
        json={"name": "Workout Bangers", "is_public": True, "description": "Heavy stuff"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Workout Bangers"
    assert body["is_public"] is True
    assert "id" in body
    assert body["track_count"] == 0


async def test_create_private_playlist(async_client):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Secret", public=False)
    assert pl["is_public"] is False


async def test_create_playlist_description_optional(async_client):
    token = await _register_and_login(async_client)
    resp = await async_client.post(
        "/playlists",
        json={"name": "No Desc", "is_public": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


# List my playlists 

async def test_list_my_playlists_returns_only_mine(async_client):
    token_a = await _register_and_login(async_client)
    token_b = await _register_and_login(async_client)

    await _create_playlist(async_client, token_a, "A's List")
    await _create_playlist(async_client, token_b, "B's List")

    resp = await async_client.get(
        "/playlists",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "A's List" in names
    assert "B's List" not in names


async def test_list_my_playlists_includes_private(async_client):
    token = await _register_and_login(async_client)
    await _create_playlist(async_client, token, "Public One", public=True)
    await _create_playlist(async_client, token, "Private One", public=False)

    resp = await async_client.get(
        "/playlists",
        headers={"Authorization": f"Bearer {token}"},
    )
    names = [p["name"] for p in resp.json()]
    assert "Private One" in names


async def test_list_my_playlists_pagination(async_client):
    token = await _register_and_login(async_client)
    for i in range(5):
        await _create_playlist(async_client, token, f"PL{i}")

    p1 = await async_client.get(
        "/playlists?limit=3&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    p2 = await async_client.get(
        "/playlists?limit=3&offset=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(p1.json()) == 3
    assert len(p2.json()) == 2


# Public browse

async def test_public_playlists_no_auth_required(async_client):
    resp = await async_client.get("/playlists/public")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_public_playlists_excludes_private(async_client):
    token = await _register_and_login(async_client)
    await _create_playlist(async_client, token, "PubVis", public=True)
    await _create_playlist(async_client, token, "PrivVis", public=False)

    resp = await async_client.get("/playlists/public")
    assert all(p["is_public"] for p in resp.json())


# Get single playlist 

# async def test_get_public_playlist_no_auth(async_client):
#     token = await _register_and_login(async_client)
#     pl = await _create_playlist(async_client, token, "Public PL", public=True)

#     resp = await async_client.get(f"/playlists/{pl['id']}", headers={"Authorization": f"Bearer {token}"})
#     assert resp.status_code == 200
#     assert resp.json()["id"] == pl["id"]


async def test_get_private_playlist_by_owner(async_client):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Private PL", public=False)
    resp = await async_client.get(
        f"/playlists/{pl['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_get_private_playlist_by_other_returns_404(async_client):
    token_owner = await _register_and_login(async_client)
    token_other = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token_owner, "Mine Only", public=False)

    resp = await async_client.get(
        f"/playlists/{pl['id']}",
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert resp.status_code == 404


async def test_get_playlist_not_found_returns_404(async_client):
    token = await _register_and_login(async_client)
    resp = await async_client.get(f"/playlists/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_get_playlist_includes_tracks(async_client, sample_tracks):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "With Tracks")

    await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": str(sample_tracks[0].id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await async_client.get(f"/playlists/{pl['id']}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    print(body)
    assert body["track_count"] == 1
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["id"] == str(sample_tracks[0].id)


# Update 

async def test_update_playlist_name(async_client):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Old Name")

    resp = await async_client.patch(
        f"/playlists/{pl['id']}",
        json={"name": "New Name", "description": "updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_update_by_non_owner_returns_404(async_client):
    token_owner = await _register_and_login(async_client)
    token_other = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token_owner, "Protected")

    resp = await async_client.patch(
        f"/playlists/{pl['id']}",
        json={"name": "Hacked", "description": None},
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert resp.status_code == 404


# Delete 

async def test_delete_playlist_success(async_client):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "To Delete")

    resp = await async_client.delete(
        f"/playlists/{pl['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Should be gone
    get_resp = await async_client.get(f"/playlists/{pl['id']}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404


async def test_delete_by_non_owner_returns_404(async_client):
    token_owner = await _register_and_login(async_client)
    token_other = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token_owner, "Owned")

    resp = await async_client.delete(
        f"/playlists/{pl['id']}",
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert resp.status_code == 404


async def test_delete_not_found_returns_404(async_client):
    token = await _register_and_login(async_client)
    resp = await async_client.delete(
        f"/playlists/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# Add track 

async def test_add_track_to_playlist(async_client, sample_tracks):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Track List")

    resp = await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": str(sample_tracks[0].id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_add_track_requires_auth(async_client, sample_tracks):
    resp = await async_client.post(
        f"/playlists/{uuid.uuid4()}/tracks",
        json={"track_id": str(sample_tracks[0].id)},
    )
    assert resp.status_code == 401


async def test_add_duplicate_track_returns_409(async_client, sample_tracks):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Dup Test")

    await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": str(sample_tracks[0].id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": str(sample_tracks[0].id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_add_unknown_track_returns_404(async_client):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "No Track")

    resp = await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# Remove track 

async def test_remove_track_from_playlist(async_client, sample_tracks):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Remove Test")
    track_id = str(sample_tracks[0].id)

    await async_client.post(
        f"/playlists/{pl['id']}/tracks",
        json={"track_id": track_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await async_client.delete(
        f"/playlists/{pl['id']}/tracks/{track_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    get_resp = await async_client.get(f"/playlists/{pl['id']}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.json()["track_count"] == 0


async def test_remove_track_not_in_playlist_returns_404(async_client, sample_tracks):
    token = await _register_and_login(async_client)
    pl = await _create_playlist(async_client, token, "Empty")

    resp = await async_client.delete(
        f"/playlists/{pl['id']}/tracks/{sample_tracks[0].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_remove_track_requires_auth(async_client, sample_tracks):
    resp = await async_client.delete(
        f"/playlists/{uuid.uuid4()}/tracks/{sample_tracks[0].id}",
    )
    assert resp.status_code == 401