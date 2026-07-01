from typing import Annotated
from fastapi import APIRouter, HTTPException, Security

from ...deps import get_current_user, SessionDep
from app.models.users import User


router = APIRouter()

@router.get("/me")
async def read_artist_me(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:read"])],
):
    """Read own artist profile"""
    if not current_user.artist_profile:
        raise HTTPException(404, "Artist profile not found")
    
    return current_user.artist_profile

@router.patch("/me")
async def update_artist_profile(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:update"])],
    session: SessionDep,
    bio: str | None = None,
    artist_name: str | None = None
):
    """Update artist profile"""
    if not current_user.artist_profile:
        raise HTTPException(404, "Artist profile not found")
    
    if bio:
        current_user.artist_profile.bio = bio
    if artist_name:
        current_user.artist_profile.artist_name = artist_name

    session.add(current_user.artist_profile)
    session.commit()

    return {"message": "Profile updated"}

@router.get("/me/analytics")
async def read_analytics(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:analytics:read"])]
):
    """Read artist analytics"""
    if not current_user.artist_profile:
        raise HTTPException(404, "Artist profile not found")
    
    return {
        "total_plays": current_user.artist_profile.total_plays,
        "monthly_listeners": current_user.artist_profile.monthly_listeners,
    }