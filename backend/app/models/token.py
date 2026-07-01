from datetime import datetime

from sqlmodel import SQLModel, Field


#schemas for authentification
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(SQLModel):
    sub: str | None = None
    scopes: list[str] = []
    role: str | None = None
    exp: int | None = None
    type: str = "access"

class RefreshRequest(SQLModel):
    refresh_token: str

class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token_hash: str = Field(index=True)
    expires_at: datetime 
    created_at: datetime = Field(default_factory=datetime.now)
    revoked_at: datetime | None = Field(default=None)

