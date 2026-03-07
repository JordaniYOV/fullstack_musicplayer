
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from typing import Annotated
from datetime import timedelta

from app.crud import user
from app.api.deps import SessionDep
from app.crud.user import authenticate
from app.core.schemas import Token
from app.core import security
from app.core.config import settings


router = APIRouter(tags=['login'])

@router.post("/login/access-token")
async def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    login with Oauth2, get an access token
    """

    User = await user.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not User:
        raise HTTPException(status_code=400, detail="Inccorernt email or password")
    elif not User.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            User.id, expires_delta=access_token_expires
        )
    )
