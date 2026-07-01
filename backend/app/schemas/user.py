import uuid

from pydantic import BaseModel, Field, EmailStr

from ..models.users import UserRole

class UserBase(BaseModel):
    username: str
    email: str
    role: UserRole

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)

class UserRegister(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    username: str | None = Field(default=None, max_length=255)

# Properties to reecieve via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=255)

class UserUpdateMe(BaseModel):
    username: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)

class UpdatePassword(BaseModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)

class UserPublic(UserBase):
    id: uuid.UUID

class UserRead(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    
    class Config:
        from_attributes = True

class ArtistProfileRead(BaseModel):
    artist_name: str
    bio: str | None
    verified: bool
    total_streams: int
    monthly_listeners: int
    
    class Config:
        from_attributes = True


# class ArtistProfileResponse(BaseModel):
#     id: uuid.UUID
#     name: str
#     bio: str | None
#     verified: bool
#     monthly_listeners: int | None
#     followers: int | None
#     album_count: int

#     class Config:
#         from_attributes = True

class AdminProfileRead(BaseModel):
    department: str | None
    access_level: int
    two_factor_enabled: bool
    
    class Config:
        from_attributes = True


class UserWithProfile(UserRead):
    artist_profile: ArtistProfileRead | None
    admin_profile: AdminProfileRead | None