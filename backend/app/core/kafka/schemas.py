import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class KafkaMessage(BaseModel): 
    """Common envelope fields present on every message"""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for the event")
    produced_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the event was produced")
    schema_version: int = Field(default = 1)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "KafkaMessage":
        return cls.model_validate_json(data.decode("utf-8"))
    

class PlayEventMessage(KafkaMessage): 
    """
    Produced by POST /charts/play after a successful play event. 
    Partitioned by track_id so all events for the same track land on the same partition, allowing for efficient aggregation.
    """
    track_id: uuid.UUID
    user_id: uuid.UUID
    duration_listened: int 
    completed: bool
    played_at: datetime

class PlayEventDLQMessage(KafkaMessage):
    """
    Wraps a failed play-event message with error context
    """
    original_topic: str
    original_partition: int
    original_offset: int
    raw_value: str 
    error_type: str
    error_message: str
    failed_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the message failed processing")

class UserLikeMessage(KafkaMessage):
    """
    Produced when a user lieks or unlikes a track / album.
    action: "like" or "unlike"
    entity_type: "track" or "album"
    """

    user_id: uuid.UUID
    entity_id: uuid.UUID
    entity_type: str
    action: str

class ChartUpdateMessage(KafkaMessage):
    """
    Produced by Celery aggregation tasks after writing tto FailyTop/WeeklyTop/MonthlyTop
    Consumers can use this to notify clients that the chart has changed.
    """

    chart_type: str
    period: str
    tracks_count: int
    aggregated_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the chart was aggregated")