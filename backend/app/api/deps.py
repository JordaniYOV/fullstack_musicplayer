
from collections.abc import Generator
from re import A
from typing import Annotated, AsyncGenerator


from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status

import jwt
import redis.asyncio as aioredis
from app.core.db import async_engine
from app.core.services.play_event import PlayEventService
from app.models.users import User
from app.core.schemas import TokenPayload
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

async def get_redis() -> AsyncGenerator[aioredis.Redis, None]: 
    """
    Dependency to get redis client
    Use to inject into endpoints
    """
    from app.core.redis.redis import get_async_redis
    redis = await get_async_redis()
    return redis

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


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


async def get_play_event_service(
        session: SessionDep,
        redis: RedisDep, 
) -> PlayEventService:
    """
    Inject PlayEventService with its dependencies
    """

    return PlayEventService(session=session, redis=redis, kafka_producer=None)

PlayEventServiceDep = Annotated(PlayEventService, Depends(get_play_event_service))