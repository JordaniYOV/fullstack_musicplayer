from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.users import CreatorProfile
from app.schemas.creator import CreatorProfileCreate, CreatorProfileUpdate


async def get_creator_by_id(session: AsyncSession, creator_id: int) -> CreatorProfile | None:
    """Get creator profile by id"""
    statement = select(CreatorProfile).where(CreatorProfile.id == creator_id)
    creator = await session.execut(statement).scalar_one_or_none()
    return creator

async def get_creator_by_user_id(session: AsyncSession, user_id: UUID): 
    """Get creator profile by user_id"""
    stmt = select(CreatorProfile).where(CreatorProfile.user_id == user_id)
    creator = await session.execute(stmt).scalar_one_or_none()
    return creator

async def create_creator_profile(
    session: AsyncSession,
    creator_in: CreatorProfileCreate
) -> CreatorProfile:
    """Create creator profile"""
    creator = CreatorProfile(
        user_id=creator_in.user_id,
        name=creator_in.name,
        type=creator_in.type,
        bio=creator_in.bio,
        verified=creator_in.verified,
        monthly_listeners=creator_in.monthly_listeners,
    )
    session.add(creator)
    await session.flush()
    await session.refresh(creator)
    return creator


async def update_creator_profile(
    session: AsyncSession,
    creator_id: UUID,
    update_data: CreatorProfileUpdate,
) -> CreatorProfile:
    """Update creator profile"""
    update_values = update_data.model_dump(exclude_unset=True)

    stmt = update(CreatorProfile).where(CreatorProfile.id == creator_id).values(**update_values).returning(Creator)
    
    result = await session.execute(stmt)
    await session.flush()
    
    updated_creator = result.scalar_one_or_none()
    return updated_creator


async def delete_creator_profile(session: AsyncSession, creator: CreatorProfile) -> None:
    """Delete creator profile"""
    await session.delete(creator)
    await session.flush()