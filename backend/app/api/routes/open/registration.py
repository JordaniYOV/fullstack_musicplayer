from typing import Any

from fastapi import APIRouter, HTTPException

from app.crud import user
from app.schemas.user import UserRegister, UserCreate, UserPublic
from app.api.deps import SessionDep

router = APIRouter()

@router.post('/signup', response_model=UserPublic)
async def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    User = await user.get_user_by_email(session=session, email=user_in.email)
    if User: 
        raise HTTPException(
            status_code=400, 
            detail="The user with this email already exists in the system",
        )    
    user_create = UserCreate.model_validate(user_in)
    User = await user.create_user(session=session, user_create=user_create)
    return User