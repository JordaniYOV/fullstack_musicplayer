from pydantic import EmailStr
from sqlmodel import SQLModel, Field

# User's Models
class UserBase(SQLModel):
    nick_name: str | None = Field(default=None, max_length=255) 
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    is_artist: bool = False

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)

class UserRegister(SQlModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)

#


