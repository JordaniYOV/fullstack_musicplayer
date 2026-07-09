from typing import Annotated
from fastapi import APIRouter, HTTPException, Security

from ...deps import get_current_user, SessionDep, CurrentUser
from app.models.users import User
from app.schemas.creator import CreatorProfileRegister

router = APIRouter()

@router.post("/create")
async def create_creator_profile(
    current_user: CurrentUser,
    artist_in: CreatorProfileRegister
):
    """Sent request to register Creator Profile. That bound to current user account."""
    


@router.get("/me")
async def read_artist_me(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:read"])],
):
    """Read own artist profile"""
    if not current_user.creator_profile:
        raise HTTPException(404, "Artist profile not found")
    
    return current_user.creator_profile

@router.patch("/me")
async def update_creator_profile(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:update"])],
    session: SessionDep,
    bio: str | None = None,
    artist_name: str | None = None
):
    """Update creator profile"""
    if not current_user.creator_profile:
        raise HTTPException(404, "Creator profile not found")
    
    if bio:
        current_user.creator_profile.bio = bio
    if artist_name:
        current_user.creator_profile.artist_name = artist_name

    session.add(current_user.creator_profile)
    session.commit()

    return {"message": "Profile updated"}

@router.get("/me/analytics")
async def read_analytics(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:analytics:read"])]
):
    """Read creator analytics"""
    if not current_user.creator_profile:
        raise HTTPException(404, "Artist profile not found")
    
    return {
        "total_plays": current_user.creator_profile.total_plays,
        "monthly_listeners": current_user.creator_profile.monthly_listeners,
    }