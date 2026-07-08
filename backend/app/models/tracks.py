from __future__ import annotations

import uuid

from typing import TYPE_CHECKING
from datetime import datetime, timedelta, date
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship, Index
from pydantic import BaseModel

if TYPE_CHECKING:
    from .users import ArtistProfile    
    from .albums import Album
    from .playlists import PlaylistTrack


class TrackBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=255)
    duration_sec: int = Field(ge=1)
    daily_plays: int = Field(default=0)
    weekly_plays: int  = Field(default=0)
    monthly_plays: int = Field(default=0)
    all_time_plays: int = Field(default=0)
    likes: int = Field(default=0)
    artist: str = Field(min_length=1, max_length=255)
    genre: str = Field(min_length=1, max_length=255)

class Track(TrackBase, table=True):
    created_at: datetime = Field(default_factory=datetime.now)
    album_id: uuid.UUID | None = Field(foreign_key="album.id", default=None, ondelete='CASCADE')
    artist_id: uuid.UUID | None = Field(foreign_key="artistprofile.id", default=None, ondelete='SET NULL')
    track_low_id: uuid.UUID | None = Field(foreign_key="tracklow.id", default=None, ondelete='SET NULL')
    track_medium_id: uuid.UUID | None = Field(foreign_key="trackmedium.id", default=None, ondelete='SET NULL')
    track_high_id: uuid.UUID | None = Field(foreign_key="trackhigh.id", default=None, ondelete='SET NULL')


    artist_profile: "ArtistProfile" | None = Relationship(back_populates="own_albums", sa_relationship_kwargs={"uselist": False})
    track_low: "TrackLow" = Relationship(back_populates="track", cascade_delete=True)
    track_medium: "TrackMedium" = Relationship(back_populates="track", cascade_delete=True)
    track_high: "TrackHigh" = Relationship(back_populates="track", cascade_delete=True)
    album: "Album" = Relationship(back_populates="tracks")
    playlists: list["PlaylistTrack"] = Relationship(back_populates="track")
    
class TrackQualityBase(SQLModel):
    audio_file: bytes
    audio_type: str 
    audio_size: int
    track_id: uuid.UUID = Field(foreign_key="track.id", ondelete='CASCADE')
    
class TrackLow(TrackQualityBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    track: "Track" = Relationship(back_populates='track_low')

class TrackMedium(TrackQualityBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    track: "Track" = Relationship(back_populates='track_medium')

class TrackHigh(TrackQualityBase, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    track: "Track" = Relationship(back_populates='track_high')

class PlayEventBase(SQLModel): 
    track_id: uuid.UUID = Field(default=None)
    user_id: uuid.UUID = Field(default=None)
    duration_listened: int = Field(default=0)
    completed: bool = Field(default=False)

class PlayEvent(PlayEventBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    played_at: datetime = Field(default_factory=datetime.now)

class PlayEventCreate(PlayEventBase): 
    pass

class PlayEventResponse(PlayEventBase):
    id: uuid.UUID
    played_at: datetime

class DailyTop(SQLModel, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chart_date: date = Field(default_factory=date.today(), nullable=False)
    track_id: uuid.UUID = Field(default=None, foreign_key="track.id", ondelete='CASCADE', nullable=False)
    play_count: int = Field(default=0)
    unique_listeners: int = Field(default=0)
    avg_listen_duration: int = Field(default=0)
    rank_position: int = Field(default=0, nullable=False)
    trend: int = Field(default=0)

    __table_args__ = (
        UniqueConstraint('chart_date', 'track_id', name='uix_daily_track'), 
        Index('idx_daily_top_date_rank', 'chart_date', 'rank_position'),
    )

class WeeklyTop(SQLModel, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    track_id: uuid.UUID = Field(default=None, foreign_key="track.id", ondelete='CASCADE', nullable=False)
    year_week: str = Field(default=None)
    week_start: datetime = Field(default_factory=datetime.now)
    week_end: datetime = Field(default_factory=lambda: datetime.now() + timedelta(weeks=1))
    play_count: int = Field(default=0)
    unique_listeners: int = Field(default=0)
    rank_position: int = Field(default=0, nullable=False)
    trend: int = Field(default=0)

    __table_args__ = (
        UniqueConstraint('year_week', 'track_id', name='uix_weekly_track'),
    )

class MonthlyTop(SQLModel, table=True): 
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    track_id: uuid.UUID = Field(default=None, foreign_key="track.id", ondelete='CASCADE', nullable=False)
    year_month: str = Field(default=None)
    month_start: datetime = Field(default_factory=datetime.now)
    month_end: datetime = Field(default_factory=lambda: datetime.now() + timedelta(weeks=4))
    play_count: int = Field(default=0)
    unique_listeners: int = Field(default=0)
    rank_position: int = Field(default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint('year_month', 'track_id', name='uix_monthly_track'),
    )

class ChartEntry(BaseModel): 
    rank: int = Field(..., ge=1, le=100)
    track_id: uuid.UUID
    title: str
    artist: str
    play_count: int
    unique_listeners: int
    trend: int | None = None
    previous_rank: int | None = None

class ChartResponse(BaseModel): 
    chart_type: str
    period: str
    generated_at: datetime = Field(default_factory=datetime)
    entries: list[ChartEntry]
    total_plays: int

class TrendingTrack(BaseModel): 
    track_id: uuid.UUID
    title: str
    artist: str
    current_rank: int
    previous_rank: int
    position_change: int
    velocity: float