from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, JSON, Column
from pydantic import EmailStr

if TYPE_CHECKING:
    from .tracks import Track
    from .albums import Album
    from .playlists import Playlist

class UserRole(str, Enum):
    GUEST = "guest" 
    USER = "user"
    ARTIST = "artist"
    ADMIN = "admin"

# User's Models
class UserBase(SQLModel):
    username: str | None = Field(default=None, max_length=255) 
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = Field(default=False, description="False if user has not confirmed email yet or has been deactivated")
    has_subscription: bool = Field(default=False, description="True if user has an active subscription")
    role: UserRole = Field(default=UserRole.USER)

# DB model
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str 
    avatar: bytes | None = Field(default=None)
    avatar_type: str | None = Field(default=None, description="MIME type of the avatar image")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None, description="the last time when user data was updated")

    liked_songs: list[uuid.UUID] | None = Field(default=None, sa_column=Column(JSON))
    own_playlists: list["Playlist"] = Relationship(back_populates="owner")
    liked_albums: list[uuid.UUID] | None = Field(default=None, sa_column=Column(JSON))

    artist_profile: "ArtistProfile" | None = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})
    admin_profile: "AdminProfile" | None = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})

    @property 
    def is_staff(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.ARTIST)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN  

    @property
    def is_artist(self) -> bool:
        return self.role == UserRole.ARTIST

    @property
    def display_name(self) -> str:
        if self.is_artist and self.artist_profile:
            return self.artist_profile.artist_name or self.username
        return self.username

class ArtistProfile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", unique=True)
    
    artist_name: str = Field(min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)

    verified: bool = False
    verified_at: datetime | None = Field(default=None, description="The date when the artist was verified by an admin")
    
    monthly_listeners: int | None = Field(default=0)
    total_plays: int | None = Field(default=0)
    followers: int | None = Field(default=0)

    own_albums: list["Album"] = Relationship(back_populates="artist", cascade_delete=True)
    user: User = Relationship(back_populates="artist_profile", sa_relationship_kwargs={"uselist": False})

class AdminProfile(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", unique=True)

    access_level: int = Field(default=1,description="1=support, 2=moderator, 3=superadmin")

    user: User = Relationship(back_populates="admin_profile", sa_relationship_kwargs={"uselist": False})

