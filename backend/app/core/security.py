from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: str | Any, scopes: list[str], role: str,  expires_delta: timedelta) -> str:
    "Create acccess token"
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "type": "access", "scopes": scopes, "role": role,"sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(
        subject: str | Any,
        expires_delta: timedelta, 
) -> str:
    "Create jwt refresh token"
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "ext": expire,
        "type": "refresh",
        "sub": str(subject),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    "Decode and validare jwt"
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != expected_type:
            raise jwt.InvalidTokenError("Wrong token type")

        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")
    
def get_token_ttl(token: str) -> int:
    """Get remaining token life in seconds"""
    payload = decode_token(token)
    exp = payload.get("exp", 0)
    now = datetime.now().timestamp()
    return max(0, int(exp - now))

def verify_password(plain_password: str, hashed_password: str) -> bool: 
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
