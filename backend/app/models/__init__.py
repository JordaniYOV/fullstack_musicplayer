from sqlmodel import SQLModel

# Сначала модели без зависимостей
from .artists import Artist

# Потом зависящие от них
from .albums import Album

# Затем остальные
from .tracks import Track

from .playlists import Playlist
from .users import User


__all__ = ["SQLModel", "Artist", "Album", "Track", "Playlist", "User"]