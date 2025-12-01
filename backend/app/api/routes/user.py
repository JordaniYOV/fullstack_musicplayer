from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.security import verify_password, get_password_hash
from app.models import UserRegister, UserCreate, UpdatePassword, Message, CurrentUser
from app.api.deps import SessionDep
from app import crud
router = APIRouter(prefix="/user", tags=["users"])


@router.post('/signup')
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user: 
        raise HTTPException(
            status_code=400, 
            detail="The user with this email already exists in the system",
        )    
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user

@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")
