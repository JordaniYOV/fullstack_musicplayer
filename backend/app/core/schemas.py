from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship
import uuid


#schemas for authentification
class Token(SQLModel): 



class UserBase(SQLModel):
    full_name: str | None = Field(default=None, max_length=255) 
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False

class User(UserBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str 
    liked_songs: list["Track"] | None = Field(default=None, sa_column=Column(JSON))
    playlists: list["Playlist"] = Relationship(back_populates="owner")
    albums: list["Album"] | None = Field(default=None, sa_column=Column(JSON))