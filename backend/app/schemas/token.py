from sqlmodel import SQLModel

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