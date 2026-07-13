from uuid import UUID
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.creator_request import create_request, get_request_by_id
from app.schemas.creator import (
    CreatorProfileRegister,
    CreatorProfileRequestResponse,
    CreatorProfileRequestStatus,
)
from app.core.kafka.producer import kafka_producer  # Твой Kafka producer
from app.core.security import get_password_hash
from app.models.users import CreatorType


class CreatorRequestServiceError(Exception):
    pass


class DuplicateRequestError(CreatorRequestServiceError):
    pass


class CreatorRequestService:
    
    @staticmethod
    async def submit_creator_request(
        session: AsyncSession,
        creator_in: CreatorProfileRegister,
    ) -> CreatorProfileRequestResponse:
        """
        User send request to register creatorprofile.
        1. Save request into bd (pending)
        2. Send event to Kafka
        3. Return request id
        """

        password_hash = get_password_hash(creator_in.password)
        
        # Сохраняем в БД
        request = await create_request(
            session=session,
            name=creator_in.name,
            email=creator_in.email,
            password_hash=password_hash,
            bio=creator_in.bio,
            type=getattr(CreatorType, creator_in.type)
        )

        request_id = request.id
        
        await kafka_producer.send(
            topic="creator.profile.requests",
            key=request_id,
            value={
                "request_id": request_id,
                "name": creator_in.name,
                "email": creator_in.email,
                "bio": creator_in.bio,
                "timestamp": datetime.now().isoformat(),
            },
        )
        
        # Уведомление админу (можно через отдельный топик или WebSocket)
        await kafka_producer.send(
            topic="admin.notifications",
            key="new_creator_request",
            value={
                "type": "new_creator_request",
                "request_id": request_id,
                "email": creator_in.email,
                "message": f"New creator profile request from {creator_in.email}",
            },
        )
        
        return CreatorProfileRequestResponse(
            request_id=request_id,
            status=CreatorProfileRequestStatus.PENDING,
            message="Your request has been submitted and is pending admin approval.",
        )
    
    @staticmethod
    async def get_request_status(
        session: AsyncSession,
        request_id: UUID,
    ) -> CreatorProfileRequestResponse:
        """Пользователь проверяет статус своей заявки."""
        request = await get_request_by_id(session=session, request_id=request_id)
        
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found",
            )
        
        message = {
            CreatorProfileRequestStatus.PENDING: "Pending admin approval.",
            CreatorProfileRequestStatus.APPROVED: "Approved! Profile created.",
            CreatorProfileRequestStatus.REJECTED: f"Rejected: {request.rejection_reason}",
        }.get(request.status, "Unknown status")
        
        return CreatorProfileRequestResponse(
            request_id=request_id,
            status=request.status,
            message=message,
        )


creator_request_service = CreatorRequestService()