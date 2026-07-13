from fastapi import APIRouter, Depends, status

from ...deps import SessionDep, get_current_admin, AdminUser
from app.schemas.creator import CreatorProfileResponse
from app.core.services.creator import create_creator_from_request
from app.core.services.creator_request import creator_request_service
from app.models.users import User

router = APIRouter(prefix="/admin/creators", tags=["admin"])


@router.post("/approve/{request_id}", response_model=CreatorProfileResponse)
async def approve_creator_request(
    session: SessionDep,
    request_id: str,
    admin: AdminUser,
):
    """
    Admin approves request and create creator profile
    """

    return await create_creator_from_request(
        session=session,
        request_id=request_id,
        admin_user=admin,
    )


@router.post("/reject/{request_id}")
async def reject_creator_request(
    session: SessionDep,
    request_id: str,
    rejection_reason: str,
    admin: User = Depends(get_current_admin),
):
    """
    Админ отклоняет заявку.
    """
    from app.crud.creator_request import update_request_status
    from app.schemas.creator import CreatorProfileRequestStatus
    
    request = await update_request_status(
        session=session,
        request_id=request_id,
        status=CreatorProfileRequestStatus.REJECTED,
        processed_by=admin.id,
        rejection_reason=rejection_reason,
    )
    
    # Уведомляем пользователя
    # await kafka_producer.send(...)
    
    return {"message": "Request rejected", "request_id": request_id}


@router.get("/requests")
async def list_pending_requests(
    session: SessionDep,
    limit: int = 50,
    offset: int = 0,
    admin: AdminUser,
):
    """Список ожидающих заявок (для админ-панели)."""
    from app.crud.creator_request import get_pending_requests
    
    return await get_pending_requests(
        session=session,
        limit=limit,
        offset=offset,
    )