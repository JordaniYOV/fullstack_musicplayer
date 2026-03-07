# from datetime import datetime, timedelta
# from tkinter import CASCADE
# import uuid

# from pydantic import EmailStr

# from sqlalchemy import null
# from sqlmodel import Relationship, SQLModel, Field, JSON, Column


# # User's Models
# class UserBase(SQLModel):
#     full_name: str | None = Field(default=None, max_length=255) 
#     email: EmailStr = Field(unique=True, index=True, max_length=255)
#     is_active: bool = True
#     is_superuser: bool = False

# # Properties to receive via API on creation
# class UserCreate(UserBase):
#     password: str = Field(min_length=8, max_length=40)

# class UserRegister(SQLModel):
#     email: EmailStr = Field(max_length=255)
#     password: str = Field(min_length=8, max_length=40)
#     full_name: str | None = Field(default=None, max_length=255)

# # Properties to reecieve via API on update, all are optional
# class UserUpdate(UserBase):
#     email: EmailStr | None = Field(default=None, max_length=255)
#     password: str | None = Field(default=None, min_length=8, max_length=255)

# class UserUpdateMe(SQLModel):
#     full_name: str | None = Field(default=None, max_length=255)
#     email: EmailStr | None = Field(default=None, max_length=255)

# class UpdatePassword(SQLModel):
#     current_password: str = Field(min_length=8, max_length=40)
#     new_password: str = Field(min_length=8, max_length=40)

# # DB model
# class User(UserBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     hashed_password: str 
#     avatar: bytes | None = Field(default=None)
#     liked_songs: list["Track"] | None = Field(default=None, sa_column=Column(JSON))
#     playlists: list["Playlist"] = Relationship(back_populates="owner")
#     albums: list["Album"] | None = Field(default=None, sa_column=Column(JSON))

# class UserPublic(UserBase):
#     id: uuid.UUID

# #Artist's models
# class ArtistBase(SQLModel):
#     photo: bytes 
#     image_type: str
#     name: str = Field(min_length=1, max_length=255)
#     bio: str | None = Field(default=None, max_length=2000)
#     verified: bool = False
#     monthly_listeners: int | None = Field(default=0)
#     plays: int | None = Field(default=0)
#     followers: int | None = Field(default=0)

# #DB Model 
# class Artist(ArtistBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     albums: list["Album"] = Relationship(back_populates="artist", cascade_delete=True)

# #Track's model
# class TrackBase(SQLModel):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track_name: str = Field(min_length=1, max_length=255)
#     duration_sec: int = Field(ge=1)
#     daily_plays: int | None = Field(default=0)
#     weekly_plays: int | None = Field(default=0)
#     monthly_plays: int | None = Field(default=0)
#     all_time_plays: int | None = Field(default=0)
#     likes: int | None = Field(default=0)
#     artist: str = Field(min_length=1, max_length=255)

# class Track(TrackBase, table=True):
#     created_at: datetime = Field(default_factory=datetime.now)
#     popular_tracks: 'PopularTracks' = Relationship(back_populates="track")
#     track_low: "TrackLow" = Relationship(back_populates="track", cascade_delete=True)
#     track_medium: "TrackMedium" = Relationship(back_populates="track", cascade_delete=True)
#     track_high: "TrackHigh" = Relationship(back_populates="track", cascade_delete=True)
#     album: "Album" = Relationship(back_populates="tracks")
#     album_id: uuid.UUID = Field(foreign_key="album.id", ondelete=CASCADE)
#     playlists: list["PlaylistTrack"] = Relationship(back_populates="track")
    

# class TrackQualityBase(SQLModel):
#     audio_file: bytes
#     audio_type: str 
#     audio_size: int
#     track_id: uuid.UUID = Field(foreign_key="track.id", ondelete=CASCADE)
    
# class TrackLow(TrackQualityBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track: "Track" = Relationship(back_populates='track_low')

# class TrackMedium(TrackQualityBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track: "Track" = Relationship(back_populates='track_medium')

# class TrackHigh(TrackQualityBase, table=True): 
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track: "Track" = Relationship(back_populates='track_high')

# class PlayEvent(SQLModel, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track_id: uuid.UUID = Field(default=None)
#     user_id: uuid.UUID = Field(default=None)
#     played_at: datetime = Field(default_factory=datetime.now)
#     duration_listened: int = Field(default=0)
#     completed: bool = Field(default=False)

# class DailyTop(SQLModel, table=True): 
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track_id: uuid.UUID = Field(default=None, foreign_key="track.id", ondelete=CASCADE)
#     play_count: int = Field(default=0)
#     data: datetime = Field(default_factory=datetime.now)

# class WeeklyTop(SQLModel, table=True): 
#     id: uuid.UUID = Field(default_factor=uuid.uuid4, primary_key=True)
#     track_id = uuid.UUID = Field(default=None, foreign_key="track.id", ondelete=CASCADE)
#     play_count: int = Field(default=0)
#     week_start: datetime = Field(default_factory=datetime.now)
#     week_end: datetime = Field(default_factory=datetime.now + timedelta(weeks=1))

# class MonthlyTop(SQLModel, table=True): 
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     track_id = uuid.UUID = Field(default=None, foreign_key="track.id", ondelete=CASCADE)
#     play_count: int = Field(default=0)
#     month_start: datetime = Field(default_factory=datetime.now)
#     month_end: datetime = Field(default_factory=datetime.now + timedelta(weeks=4))

# # class PopularTracks(SQLModel, table=True): 
# #     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
# #     track_id: uuid.UUID = Field(foreign_key="track.id", ondelete=CASCADE)
# #     period: str 
# #     play_count: int 
# #     calculated_at: datetime = Field(default_factory=datetime.now)
# #     track: "Track" = Relationship(back_populates='popular_tracks')


# #Album's model
# class AlbumBase(SQLModel):
#     album_name: str = Field(min_length=1, max_length=255)
#     artist_name: str = Field(min_length=1, max_length=255) 
#     total_tracks: int 
#     play_count: int 
#     year_release: int = Field(le=3000, ge=1000)
    
# #DB model
# class Album(AlbumBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     artist_id: uuid.UUID = Field(foreign_key="artist.id", ondelete=CASCADE)
#     artist: "Artist" = Relationship(back_populates="albums")
#     tracks: list["Track"] = Relationship(back_populates="album", cascade_delete=True)
#     cover: "AlbumsCover" = Relationship(back_populates="album", cascade_delete=True)

# #Album cover table
# class AlbumsCover(SQLModel, table=True): 
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     album_id: uuid.UUID = Field(foreign_key="album.id", ondelete=CASCADE)
#     album_cover: bytes
#     cover_type: str 
    

# #Popular albums
# class PopularAlbums(SQLModel, table=True): 
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     album_id: uuid.UUID = Field(foreign_key="album.id", ondelete=CASCADE)
#     period: str 
#     play_count: int
#     calculated_at: datetime = Field(default_factory=datetime.now)
#     album: "Album" = Relationship(back_populates="popular_albums")

# #Conecting model for tracks in playlists 
# class PlaylistTrack(SQLModel, table=True):
#     playlist_id: uuid.UUID = Field(foreign_key="playlist.id", primary_key=True)
#     track_id: uuid.UUID = Field(foreign_key="track.id", primary_key=True)

#     playlist: "Playlist" = Relationship(back_populates="tracks")
#     track: "Track" = Relationship(back_populates="playlists")


# #Playlist's models
# class PlaylistBase(SQLModel):
#     name: str = Field(min_length=1, max_length=255)
#     description: str | None = Field(default=None, max_length=255)
#     is_public: bool = False

# #Properties to receive on item creation
# class PlaylistCreate(PlaylistBase):
#     pass

# #Properties to receive on item update
# class PlaylistUpdate(PlaylistBase):
#     name: str = Field(min_length=1, max_length=255)
#     description: str | None = Field(default=None, max_length=255)

# #DB Model, database table inferred from class name
# class Playlist(PlaylistBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

#     owner_id: uuid.UUID = Field(foreign_key="user.id")
#     owner: "User" = Relationship(back_populates="playlists")
#     tracks: list["PlaylistTrack"] = Relationship(back_populates="playlist")

# # Properties to recieve via API
# class PlaylistPublic(PlaylistBase):
#     pass

# class Message(SQLModel):
#     message: str


# # JSON payload containing access token
# class Token(SQLModel):
#     access_token: str
#     token_type: str = "bearer"

# class TokenPayload(SQLModel):
#     sub: str | None = None
