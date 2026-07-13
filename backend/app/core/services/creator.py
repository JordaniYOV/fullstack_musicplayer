from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.creator import create_creator_profile, get_creator_by_user_id, update_creator_profile
from app.crud.creator_request import get_request_by_id, update_request_status
from app.schemas.creator import CreatorProfileRequestStatus, CreatorProfileCreate, CreatorProfileUpdate
from app.crud.user import get_user_by_email, create_user
from app.models.users import User, UserRole, CreatorProfile
from app.schemas.user import UserCreate


class CreatorServiceError(Exception):
    """Базовое исключение сервиса."""
    pass


class CreatorProfileAlreadyExistsError(CreatorServiceError):
    pass


class UserCreationError(CreatorServiceError):
    pass


async def create_creator_from_request(
        session: AsyncSession,
        request_id: UUID,
        admin_user: User,
    ) -> CreatorProfile:
        """
        Admin create creator profile from approved request.
        Called by admin route or kafka consumer.
        """
        request = await get_request_by_id(session=session, request_id=request_id)
        
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found",
            )
        
        if request.status != CreatorProfileRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Request already {request.status}",
            )
        
        existing_user = await get_user_by_email(session=session, email=request.email)
        
        if existing_user and existing_user.creator_profile:
            await update_request_status(
                session=session,
                request_id=request_id,
                status=CreatorProfileRequestStatus.REJECTED,
                processed_by=admin_user.id,
                rejection_reason="Creator profile already exists for this email",
            )
            raise CreatorProfileAlreadyExistsError(
                "Creator profile already exists for this user"
            )
        
        if not existing_user:
            try:
                user_create = UserCreate(
                    username=request.name,
                    email=request.email,
                    role=UserRole.ARTIST,
                    password=request.password_hash,  
                )
                user = await create_user(session=session, user_create=user_create)
            except Exception as e:
                raise UserCreationError(f"Failed to create user: {str(e)}") from e
        else:
            user = existing_user
            user.role = UserRole.ARTIST
            session.add(user)

        creator_profile = CreatorProfileCreate(
            user_id=user.id, 
            name=request.name,
            type=request.type, 
            bio=request.bio,
            verified=False,
            monthly_listeners=0
        )

        creator = await create_creator_profile(
            session=session,
            creator_in=creator_profile,
        )
        
        await update_request_status(
            session=session,
            request_id=request_id,
            status=CreatorProfileRequestStatus.APPROVED,
            processed_by=admin_user.id,
        )
        
        return creator

async def get_own_profile(
        session: AsyncSession,
        current_user: User,
    ) -> CreatorProfile:
        creator = await get_creator_by_user_id(session=session, user_id=current_user.id)
        if not creator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Creator profile not found",
            )
        return creator
    
async def update_own_profile(
        session: AsyncSession,
        creator_id: UUID,
        update_data: CreatorProfileUpdate,
    ) -> CreatorProfile:
        return await update_creator_profile(
            session=session,
            creator_id=creator_id,
            update_data=update_data,
        )

async def get_analytics(current_user: User) -> dict:
        if not current_user.creator_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Creator profile not found",
            )
        return {
            "total_plays": current_user.creator_profile.total_plays,
            "monthly_listeners": current_user.creator_profile.monthly_listeners,
        }
    