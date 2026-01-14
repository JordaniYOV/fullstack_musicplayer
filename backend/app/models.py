from datetime import datetime
from tkinter import CASCADE
import uuid

from pydantic import EmailStr
from pydantic.types import condecimal

from sqlmodel import Relationship, SQLModel, Field, JSON, Column


# User's Models
class UserBase(SQLModel):
    full_name: str | None = Field(default=None, max_length=255) 
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False

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

# DB model
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str 
    liked_songs: list["Track"] | None = Field(default=None, sa_column=Column(JSON))
    playlists: list["Playlist"] = Relationship(back_populates="owner")
    albums: list["Album"] | None = Field(default=None, sa_column=Column(JSON))

class UserPublic(UserBase):
    id: uuid.UUID

#Artist's models
class ArtistBase(SQLModel):
    photo: bytes 
    image_type: str
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)
    verified: bool = False
    monthly_listeners: int 

#DB Model 
class Artist(ArtistBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    albums: list["Album"] = Relationship(back_populates="artist")

#Track's model
class TrackBase(SQLModel):
    track_name: str = Field(min_length=1, max_length=255)
    duration_sec: int = Field(ge=1)
    audio_file: bytes 
    audio_type: str 
    audio_size: int
    album_id: uuid.UUID = Field(foreign_key="album.id", ondelete=CASCADE)
    
class Track(TrackBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)     album: "Album" = Relationship(back_populates="tracks")
    playlists: list["PlaylistTrack"] = Relationship(back_populates="track")

#Album's model
class AlbumBase(SQLModel):
    album_name: str = Field(min_length=1, max_length=255)
    album_cover: bytes 
    image_type: str 
    total_tracks: int 
    year_release: int = Field(le=3000, ge=1000)
    
#DB model
class Album(AlbumBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    artist_id: uuid.UUID = Field(foreign_key="artist.id")
    artist: "Artist" = Relationship(back_populates="albums")
    tracks: list["Track"] = Relationship(back_populates="album", cascade_delete=True)

#Conecting model for tracks in playlists 
class PlaylistTrack(SQLModel, table=True):
    playlist_id: uuid.UUID = Field(foreign_key="playlist.id", primary_key=True)
    track_id: uuid.UUID = Field(foreign_key="track.id", primary_key=True)

    playlist: "Playlist" = Relationship(back_populates="tracks")
    track: "Track" = Relationship(back_populates="playlists")


#Playlist's models
class PlaylistBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    is_public: bool = False

#Properties to receive on item creation
class PlaylistCreate(PlaylistBase):
    pass

#Properties to receive on item update
class PlaylistUpdate(PlaylistBase):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)

#DB Model, database table inferred from class name
class Playlist(PlaylistBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: "User" = Relationship(back_populates="playlists")
    tracks: list["PlaylistTrack"] = Relationship(back_populates="playlist")

# Properties to recieve via API
class PlaylistPublic(PlaylistBase):
    pass

class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(SQLModel):
    sub: str | None = None
