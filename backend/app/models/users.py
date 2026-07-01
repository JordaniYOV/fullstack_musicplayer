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

class Scope(str, Enum):
     
    # ===== SYSTEM =====
    SYSTEM_INFRA = "system:infra"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_METRICS = "system:metrics"
    
    # ===== ADMIN =====
    ADMIN_USERS_READ = "admin:users:read"
    ADMIN_USERS_UPDATE = "admin:users:update"
    ADMIN_USERS_DELETE = "admin:users:delete"
    ADMIN_ARTISTS_VERIFY = "admin:artists:verify"
    ADMIN_ARTISTS_DELETE = "admin:artists:delete"
    ADMIN_ALBUMS_DELETE = "admin:albums:delete"
    ADMIN_TRACKS_DELETE = "admin:tracks:delete"
    ADMIN_CHARTS_BACKFILL = "admin:charts:backfill"
    ADMIN_HEALTH_READ = "admin:health:read"
    
    # ===== ARTIST =====
    ARTIST_PROFILE_READ = "artist:profile:read"
    ARTIST_PROFILE_UPDATE = "artist:profile:update"
    ARTIST_ALBUMS_CREATE = "artist:albums:create"
    ARTIST_ALBUMS_UPDATE = "artist:albums:update"
    ARTIST_ALBUMS_DELETE = "artist:albums:delete"
    ARTIST_TRACKS_CREATE = "artist:tracks:create"
    ARTIST_TRACKS_UPDATE = "artist:tracks:update"
    ARTIST_TRACKS_DELETE = "artist:tracks:delete"
    ARTIST_ANALYTICS_READ = "artist:analytics:read"
    
    # ===== USER =====
    USER_PROFILE_READ = "user:profile:read"
    USER_PROFILE_UPDATE = "user:profile:update"
    USER_PROFILE_DELETE = "user:profile:delete"
    USER_LIBRARY_READ = "user:library:read"
    USER_LIBRARY_WRITE = "user:library:write"
    USER_FOLLOW_WRITE = "user:follow:write"
    USER_PLAYLISTS_READ = "user:playlists:read"
    USER_PLAYLISTS_WRITE = "user:playlists:write"
    USER_PLAYLISTS_TRACKS_WRITE = "user:playlists:tracks:write"
    USER_PLAY_WRITE = "user:play:write"
    USER_HISTORY_READ = "user:history:read"
    USER_SEARCH_READ = "user:search:read"
    
    # ===== GUEST =====
    CATALOG_READ = "catalog:read"
    CHARTS_READ = "charts:read"
    SEARCH_READ = "search:read"
    STREAM_READ = "stream:read"

    @staticmethod
    def scopes(scopes: set) -> set["Scope"]:
        result = set()
        for scope in scopes:
            if scope.endswith(":*"):
                prefix = scope[:-2]
                result.update(s for s in Scope if s.value.startswith(prefix))
            
            result.add(Scope.scope)

        return result

class UserRole(str, Enum):
    GUEST = "guest" 
    USER = "user"
    ARTIST = "artist"
    ADMIN = "admin"

    SCOPES = { 
        GUEST: {"guest:*"},
        USER: {"user:*"},
        ADMIN: {"admin:*", "system:*"},
    }

# User's Models
class UserBase(SQLModel):
    full_name: str | None = Field(default=None, max_length=255) 
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = Field(default=False, description="true when user is logged in, false when not")
    is_verified: bool = Field(default=False)
    is_superuser: bool = Field(default=False, description="true if user has a subscribtion")
    role: UserRole = Field(default=UserRole.USER)

    #artist porperty
    artist_name: str | None = Field(default=None, description="used when user also are artist")
    artist_verified: bool = Field(default=False)

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)

class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)

# Properties to reecieve via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=255)

class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)

class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)

class UserPublic(UserBase):
    id: uuid.UUID

# DB model
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str 
    avatar: bytes | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None, description="the last time when user data was updated")

    liked_songs: list[uuid.UUID] | None = Field(default=None, sa_column=Column(JSON))
    playlists: list["Playlist"] = Relationship(back_populates="owner")
    albums: list[uuid.UUID] | None = Field(default=None, sa_column=Column(JSON))

    @property 
    def is_staff(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.ARTIST)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN        
