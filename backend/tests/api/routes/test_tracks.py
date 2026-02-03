import random

from fastapi.testclient import TestClient
from sqlmodel import Session
from tests.utils.track import get_all_tracks_id

def test_increase_plays(client: TestClient, db: Session):
    tracks_id = get_all_tracks_id(db)

    for track_id in tracks_id: 
        plays = random.randint(0, 1000)
        data = {
            "plays": plays, 
            "track_id": f'{track_id}', 
            "period": "day"
        }
        response = client.patch("/track/add_plays", params=data)
        assert response.status_code == 200

