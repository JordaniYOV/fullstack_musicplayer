
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from typing import Annotated
from datetime import timedelta

from app.core.services.role_scope import RoleScopeSevice
from app.api.deps import SessionDep
from app.crud.user import authenticate
from app.schemas.token import Token
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

    User = await authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not User:
        raise HTTPException(status_code=400, detail="Inccorernt email or password")
    elif not User.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refersh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    scopes = [s.value for s in RoleScopeSevice.get_scopes(User.role.value)]
   
    access_token=security.create_access_token(subject=User.id, expires_delta=access_token_expires, scopes=scopes, role=User.role.value)
    refresh_token=security.create_refresh_token(subject=User.id, expires_delta=refersh_token_expires)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer", 
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  
    )