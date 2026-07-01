from typing import Annotated
from fastapi import APIRouter, HTTPException, Security

from ...deps import SessionDep, get_current_user
from app.models.users import User

router = APIRouter()

@router.post("/me/album")
async def create_album(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:albums:create"])],
    session: SessionDep, 
    # album_data: AlbumCreate,
):
    """Create album"""
    if not current_user.artist_profile:
        raise HTTPException(403, "Artist verification required")
    
    ...

