import uuid
from typing import TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .artists import Artist
    from .tracks import Track

#Album's model
class AlbumBase(SQLModel):
    album_name: str = Field(min_length=1, max_length=255)
    artist_name: str = Field(min_length=1, max_length=255) 
    total_tracks: int 
    play_count: int = Field(default=0)
    year_release: int = Field(le=3000, ge=1000)
    
#DB model
class Album(AlbumBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    artist_id: uuid.UUID = Field(foreign_key="artist.id", ondelete='CASCADE')
    artist: "Artist" = Relationship(back_populates="albums")
    tracks: list["Track"] = Relationship(back_populates="album", cascade_delete=True)
    cover_id: uuid.UUID = Field(foreign_key='albumscover.id', ondelete="CASCADE")
    cover: "AlbumsCover" = Relationship(back_populates="album")

#Album cover table
class AlbumsCover(SQLModel, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    album_cover: bytes
    cover_type: str 
    
    album: "Album" = Relationship(back_populates="cover")

#Popular albums
class PopularAlbums(SQLModel, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    album_id: uuid.UUID = Field(foreign_key="album.id", ondelete='CASCADE')
    period: str 
    play_count: int
    calculated_at: datetime = Field(default_factory=datetime.now)
    # album: "Album" = Relationship(back_populates="popular_albums")
