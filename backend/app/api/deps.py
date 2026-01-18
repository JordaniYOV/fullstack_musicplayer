from collections.abc import Generator
from typing import Annotated


from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status
import jwt
from app.core.db import engine
from app.models import TokenPayload, User
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from app.core import security



reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/login/access-token"
)

async def get_db() -> Generator[AsyncSession, None, None]:
    async with AsyncSession(engine) as session: 
        try:
            yield session
            await session.commit()
        except Exception: 
            await session.rollback()
            raise
        finally: 
            await session.close()

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]