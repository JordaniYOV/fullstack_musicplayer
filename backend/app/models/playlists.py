import uuid
from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .users import User
    from .tracks import Track

#Conecting model for tracks in playlists 
class PlaylistTrack(SQLModel, table=True):
    playlist_id: uuid.UUID = Field(foreign_key="playlist.id", primary_key=True)
    track_id: uuid.UUID = Field(foreign_key="track.id", primary_key=True)

    playlist: "Playlist" = Relationship(back_populates="tracks")
    track: "Track" = Relationship(back_populates="playlists")
    order: int = Field(default=0, description="The order of the track in the playlist")

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