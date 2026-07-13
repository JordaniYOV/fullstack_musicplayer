from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.users import CreatorProfileRequest
from app.schemas.creator import CreatorProfileRequestStatus, CreatorType


async def create_request(
    session: AsyncSession,
    name: str,
    email: str,
    hashed_password: str,  
    bio: str | None = None,
    type: CreatorType 
) -> CreatorProfileRequest:
    """Создать заявку в БД."""
    request = CreatorProfileRequest(
        name=name,
        email=email,
        hashed_password=hashed_password,
        bio=bio,
        type=type,
        status=CreatorProfileRequestStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    await session.refresh(request)
    return request


async def get_request_by_id(
    session: AsyncSession,
    request_id: UUID,
) -> CreatorProfileRequest | None:
    """Получить заявку по ID."""
    result = await session.execute(
        select(CreatorProfileRequest).where(CreatorProfileRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def get_pending_requests(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[CreatorProfileRequest]:
    """Получить список ожидающих заявок."""
    result = await session.execute(
        select(CreatorProfileRequest)
        .where(CreatorProfileRequest.status == CreatorProfileRequestStatus.PENDING)
        .order_by(CreatorProfileRequest.created_at)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def update_request_status(
    session: AsyncSession,
    request_id: UUID,
    status: CreatorProfileRequestStatus,
    processed_by: UUID,
    rejection_reason: str | None = None,
) -> CreatorProfileRequest | None:
    """Обновить статус заявки."""
    result = await session.execute(
        update(CreatorProfileRequest)
        .where(CreatorProfileRequest.id == request_id)
        .values(
            status=status,
            processed_at=datetime.now(),
            processed_by=processed_by,
            rejection_reason=rejection_reason,
        )
        .returning(CreatorProfileRequest)
    )
    await session.flush()
    return result.scalar_one_or_none()