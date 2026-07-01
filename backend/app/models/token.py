from datetime import datetime

from sqlmodel import SQLModel, Field


class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token_hash: str = Field(index=True)
    expires_at: datetime 
    created_at: datetime = Field(default_factory=datetime.now)
    revoked_at: datetime | None = Field(default=None)

