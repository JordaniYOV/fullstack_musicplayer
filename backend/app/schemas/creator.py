from uuid import UUID
from pydantic import BaseModel

from ..models.users import CreatorType

class CreatorProfileCreate(BaseModel):
    email: str
    password: str
    name: str
    bio: str | None = None
    verifeid: bool = False
    monthly_listeners: int = 0

class CreatorProfileRegister(BaseModel):
    emial: str
    name: str
    bio: str | None = None
    type: CreatorType