from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship
import uuid


#schemas for authentification
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(SQLModel):
    sub: str | None = None
