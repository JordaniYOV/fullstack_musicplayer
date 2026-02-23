
from collections.abc import Generator
from typing import Annotated, AsyncGenerator


from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status

import jwt
import redis.asyncio as redis
from app.core.db import async_engine
from app.models import TokenPayload, User
from app.core.redis.redis import redis_client
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from app.core import security



reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/login/access-token"
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session: 
        yield session

async def get_redis() -> AsyncGenerator[redis.Redis, None]: 
    """
    Dependency to get redis client
    Use to inject into endpoints
    """
    client = await redis_client.get_client()
    
    try: 
        yield client
    finally: 
        pass

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
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
    user = await session.get(User, token_data.sub)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]