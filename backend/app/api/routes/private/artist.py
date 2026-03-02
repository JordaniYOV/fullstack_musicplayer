from fastapi import APIRouter, UploadFile

from app.api.deps import SessionDep
from app.models import Artist

router = APIRouter(tags=["artist_private"])

@router.post('/add/artist')
async def add_artist(session: SessionDep,
                    photo: UploadFile, 
                    name: str, 
                    bio: str | None = None, 
                    monthly_listeners: int = 120,
                    verified: bool = False
): 
    """
    Add new Artist
    """
    image_type = photo.content_type
    image = await photo.read()
    artist = Artist(
        photo=image, 
        image_type=image_type, 
        name=name, 
        bio=bio, 
        verified=verified,
        monthly_listeners=monthly_listeners,
    )
    session.add(artist)
    await session.commit()
