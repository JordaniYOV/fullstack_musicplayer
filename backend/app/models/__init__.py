from sqlmodel import SQLModel

# Потом зависящие от них
from .albums import Album

# Затем остальные
from .tracks import Track

from .playlists import Playlist
from .users import User


__all__ = ["SQLModel", "Album", "Track", "Playlist", "User"]