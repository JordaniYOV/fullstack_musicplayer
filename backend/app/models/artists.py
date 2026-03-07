import uuid

from sqlmodel import SQLModel, Field, Relationship

#Artist's models
class ArtistBase(SQLModel):
    photo: bytes 
    image_type: str
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2000)
    verified: bool = False
    monthly_listeners: int | None = Field(default=0)
    plays: int | None = Field(default=0)
    followers: int | None = Field(default=0)

#DB Model 
class Artist(ArtistBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    albums: list["Album"] = Relationship(back_populates="artist", cascade_delete=True)