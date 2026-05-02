from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_validator


class PlayRequest(BaseModel):
    """Body sent by the client when a track is played."""
    
    track_id: uuid.UUID
    duration_listened: int = Field(ge=0, description="Seconds the user actually listened")
    completed: bool = Field(defualt=False, description="True if the user listened to the full track")

    @field_validator("duration_listened")
    @classmethod
    def duration_must_be_resonable(cls, v: int) -> int:
        if v > 14_400:
            raise ValueError("duration_listened exceeds max allowed value (14 000 s)")
        return v
    
class PlayResponse(BaseModel):
    """Return to the client after processing the play event."""

    event_id: uuid.UUID
    track_id: uuid.UUID
    recorded_at: datetime
    deduplicated: bool = Field(default=False, description="True when this play was a duplicate within the dedup window "
                    "and was NOT persisted again.")
    message: str = Field(default="Play event recorded successfully.")

class CounterUpdate(BaseModel): 
    """Internal -passed to the Celery recount task."""

    track_id: str
    daily_plays: int
    weekly_plays: int
    monthly_plays: int
    all_time_plays: int

class PlayEventPublic(BaseModel): 
    """Returned by GET /charts/play/history (per-user history endpoint)"""

    event_id: uuid.UUID
    track_id: uuid.UUID
    duration_listened: int
    completed: bool
    played_at: datetime

    class Config:
        from_attributes = True