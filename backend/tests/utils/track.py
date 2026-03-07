import uuid

from sqlmodel import Session, select
from app.models.tracks import Track

def get_all_tracks_id(session: Session): 
    statement = select(Track.id)
    tracks_id = session.exec(statement).all()

    return tracks_id