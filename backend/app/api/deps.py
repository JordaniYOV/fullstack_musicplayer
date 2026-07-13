import jwt
import redis.asyncio as aioredis

from typing import Annotated, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import SecurityScopes

from app.core.db import async_engine
from app.core.services.play_event import PlayEventService
from app.models.users import User
from app.schemas.token import TokenPayload
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.models.users import UserRole



reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/login/access-token",
     scopes={
        "user:profile:read": "Read own profile",
        "user:profile:update": "Update own profile",
        "user:library:read": "Read library",
        "user:library:write": "Modify library",
        "artist:profile:read": "Read artist profile",
        "artist:albums:create": "Create albums",
        "artist:tracks:create": "Create tracks",
        "artist:analytics:read": "Read artist analytics",
        "admin:users:read": "Read all users",
        "admin:users:delete": "Delete users",
        "admin:artists:verify": "Verify artists",
        "system:config": "System configuration",
        "catalog:read": "Read catalog",
        "stream:read": "Stream music",
    },
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session: 
        try:
            yield session
        finally:
            await session.rollback()

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


async def get_current_user(session: SessionDep, token: TokenDep, security_scopes: SecurityScopes) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    token_scopes = set(token.get("scopes", []))
    required_scopes = set(security_scopes.scopes)

    if required_scopes and not required_scopes.issubset(token_scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not enough permissions. Required: {required_scopes}"
        )
    statement = (
        select(User)
        .where(User.id == token_data.sub)
        .options(
            selectinload(User.artist_profile), 
            selectinload(User.admin_profile),
        )
    )
    user = await session.exec(statement).all()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

async def require_admin(
        current_user: Annotated[User, Security(get_current_user, scopes=["admin:users:read"])]
) -> User:
    """Ensure user is admin"""
    if not current_user.role == UserRole.ADMIN  or not current_user.admin_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def require_artist(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:read"])],
) -> User:
    """Ensure user is artist or admin."""
    if current_user.role != UserRole.Artist or not current_user.artist_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Artist access required",
        )
    return current_user

async def require_verified_artist(
    current_user: Annotated[User, Security(get_current_user, scopes=["artist:profile:read"])],
) -> User:
    """Ensure user is verified artist."""
    if current_user.role == UserRole.ADMIN:
        return current_user
    if current_user.role != UserRole.ARTIST or not current_user.artist_profile.artist_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified artist access required",
        )
    return current_user

AdminUser = Annotated[User, Depends(require_admin)]
ArtistUser = Annotated[User, Depends(require_artist)]
VerifiedArtistUser = Annotated[User, Depends(require_verified_artist)]

async def get_play_event_service(
        session: SessionDep,
        redis: RedisDep, 
) -> PlayEventService:
    """
    Inject PlayEventService with its dependencies
    """

    return PlayEventService(session=session, redis=redis, kafka_producer=None)

PlayEventServiceDep = Annotated[PlayEventService, Depends(get_play_event_service)]