from typing import Annotated
from fastapi import APIRouter, Security, status
from fastapi.exceptions import HTTPException

from ...deps import get_current_user, SessionDep, CurrentUser, ArtistUser
from app.schemas.creator import (
    CreatorProfileRegister,
    CreatorProfileRequestResponse,
    CreatorProfileUpdate,
)
from app.core.services.creator_request import creator_request_service
from app.core.services.creator import get_own_profile, update_own_profile, get_analytics
from app.models.users import User

router = APIRouter()


@router.post("/request", status_code=status.HTTP_202_ACCEPTED)
async def request_creator_profile(
    session: SessionDep,
    current_user: CurrentUser, 
    creator_in: CreatorProfileRegister,
):
    """
    User send request to create creator profile.
    Request goes to kafka and admin recieve notification
    """
    if current_user.artist_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a creator profile",
    )

    return await creator_request_service.submit_creator_request(
        session=session,
        creator_in=creator_in,
    )


@router.get("/request/{request_id}")
async def check_request_status(
    session: SessionDep,
    current_user: CurrentUser, 
    request_id: str,
):
    """Check request status"""
    return await creator_request_service.get_request_status(
        session=session,
        request_id=request_id,
    )


@router.get("/me")
async def read_creator_me(
    session: SessionDep,
    current_user: ArtistUser,
):
    """Get own creator profile"""
    return await get_own_profile(
        session=session,
        current_user=current_user,
    )


@router.patch("/me")
async def update_creator_profile(
    session: SessionDep,
    current_user: ArtistUser,
    update_data: CreatorProfileUpdate,
):
    """Update own creator profile"""
    return await update_own_profile(
        session=session,
        current_user=current_user,
        update_data=update_data,
    )


@router.get("/me/analytics")
async def read_analytics(
    current_user: ArtistUser,
):
    """Get creator analytics"""
    return await get_analytics(current_user=current_user)