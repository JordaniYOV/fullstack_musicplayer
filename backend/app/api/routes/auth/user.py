from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.security import verify_password, get_password_hash
from app.schemas.user import UpdatePassword, UserPublic, UserUpdateMe
from app.models.token import Message
from app.api.deps import CurrentUser, SessionDep
from app.crud import user

router = APIRouter(prefix="/user", tags=["users"])


#Profile

@router.patch("/me/password", response_model=Message)
async def update_password_me(
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
    await session.commit()
    return Message(message="Password updated successfully")

@router.patch("/me/update", response_model=UserPublic)
async def update_info(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any: 
    """
    Update email and name
    """
    if user_in.email: 
        existing_user = await user.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id: 
            raise HTTPException(
                status_code=409, detail="User with this email already extists"
            )
    
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user

@router.put("/me/avatar", response_model=Message)
async def update_avatar(session: SessionDep, current_user: CurrentUser, avatar: UploadFile): 
    """
    Update own avatar
    """

    if avatar: 
        content = await avatar.read()
        current_user.avatar = content

    session.add(current_user)
    await session.commit()
    
    return Message(message="Avatar have been updated")

@router.delete("/me/delete")
async def delete_me(
    *, session: SessionDep, current_user: CurrentUser
) -> Any: 
    """
    delete my account
    """
    await session.delete(current_user)
    await session.commit()
    return Message(message="Your acc was deleted")

#Settings
@router.get("me/settings")
async def get_current_settings(session: SessionDep, current_user: CurrentUser): 
    return current_user

@router.patch("me/settings/update")
async def update_settings(session: SessionDep, current_user: CurrentUser): 
    return current_user


