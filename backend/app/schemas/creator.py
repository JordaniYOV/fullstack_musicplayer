from uuid import UUID
from pydantic import BaseModel
from enum import Enum

from ..models.users import CreatorType

class CreatorProfileRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class CreatorProfileRegister(BaseModel):
    email: str
    password: str 
    name: str
    bio: str | None = None
    type: CreatorType

class CreatorProfileRequestResponse(BaseModel):
    """Ответ пользователю после подачи заявки."""
    request_id: str
    status: CreatorProfileRequestStatus
    message: str

# class CreatorCreate(BaseModel):
#     email: str
#     name: str
#     bio: str | None = None
#     type: CreatorType

class CreatorProfileCreate(BaseModel):
    user_id: UUID
    name: str
    type: CreatorType
    bio: str | None = None
    verified: bool = False
    monthly_listeners: int = 0
    total_listeners: int = 0

class CreatorProfileUpdate(BaseModel):
    """Schema to update creator profile"""
    bio: str | None = None
    name: str | None = None
    type: CreatorType | None = None
    verified: bool | None = None
    monthly_listeners: int | None = None
    total_listeners: int | None = None

class CreatorProfileResponse(BaseModel):
    id: int
    name: str
    bio: str | None
    type: CreatorType
    verified: bool
    monthly_listeners: int
    total_plays: int
    user_id: int
    
    class Config:
        from_attributes = True

