from dataclasses import dataclass
from enum import Enum

class Scope(str, Enum):
    """Permission scopes. Pure data, no business logic"""

    # ===== SYSTEM =====
    SYSTEM_INFRA = "system:infra"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_METRICS = "system:metrics"
    
    # ===== ADMIN =====
    ADMIN_USERS_READ = "admin:users:read"
    ADMIN_USERS_UPDATE = "admin:users:update"
    ADMIN_USERS_DELETE = "admin:users:delete"
    ADMIN_ARTISTS_VERIFY = "admin:artists:verify"
    ADMIN_ARTISTS_DELETE = "admin:artists:delete"
    ADMIN_ALBUMS_DELETE = "admin:albums:delete"
    ADMIN_TRACKS_DELETE = "admin:tracks:delete"
    ADMIN_CHARTS_BACKFILL = "admin:charts:backfill"
    ADMIN_HEALTH_READ = "admin:health:read"
    
    # ===== ARTIST =====
    ARTIST_PROFILE_READ = "artist:profile:read"
    ARTIST_PROFILE_UPDATE = "artist:profile:update"
    ARTIST_ALBUMS_CREATE = "artist:albums:create"
    ARTIST_ALBUMS_UPDATE = "artist:albums:update"
    ARTIST_ALBUMS_DELETE = "artist:albums:delete"
    ARTIST_TRACKS_CREATE = "artist:tracks:create"
    ARTIST_TRACKS_UPDATE = "artist:tracks:update"
    ARTIST_TRACKS_DELETE = "artist:tracks:delete"
    ARTIST_ANALYTICS_READ = "artist:analytics:read"
    
    # ===== USER =====
    USER_PROFILE_READ = "user:profile:read"
    USER_PROFILE_UPDATE = "user:profile:update"
    USER_PROFILE_DELETE = "user:profile:delete"
    USER_LIBRARY_READ = "user:library:read"
    USER_LIBRARY_WRITE = "user:library:write"
    USER_FOLLOW_WRITE = "user:follow:write"
    USER_PLAYLISTS_READ = "user:playlists:read"
    USER_PLAYLISTS_WRITE = "user:playlists:write"
    USER_PLAYLISTS_TRACKS_WRITE = "user:playlists:tracks:write"
    USER_PLAY_WRITE = "user:play:write"
    USER_HISTORY_READ = "user:history:read"
    USER_SEARCH_READ = "user:search:read"
    
    # ===== GUEST =====
    CATALOG_READ = "catalog:read"
    CHARTS_READ = "charts:read"
    SEARCH_READ = "search:read"
    STREAM_READ = "stream:read"
    
    @classmethod
    def from_string(cls, value: str) -> "Scope":
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid scope: {value}")
        

@dataclass(frozen=True)
class RoleConfig:
    name: str
    scope_patterns: set[str]
    description: str = ""

class RoleScopeSevice:
    """Maps roles to scopes. Can be loaded from DB, file, or env."""
    
    _CONFIG = {
        "guest": RoleConfig(
            name="guest",
            scope_patterns={"catalog:*", "charts:*", "search:*", "stream:*"},
            description="Unauthenticated user",
        ),
        "user": RoleConfig(
            name="user",
            scope_patterns={
                "user:*",
                "catalog:*", "charts:*", "search:*", "stream:*",
            },
        ),
        "artist": RoleConfig(
            name="artist",
            scope_patterns={
                "artist:*",
                "user:*",
                "catalog:*", "charts:*", "search:*", "stream:*",
            },
        ),
        "admin": RoleConfig(
            name="admin",
            scope_patterns={"*"},
            description="Full access",
        ),
    }
    
    @classmethod
    def get_scopes(cls, role: str) -> set[Scope]:
        """Resolve wildcard patterns to concrete scopes."""
        config = cls._CONFIG.get(role)
        if not config:
            return set()
        
        result: set[Scope] = set()

        for pattern in config.scope_patterns:
            if pattern == "*":
                return set(Scope)
            
            if pattern.endswith(":*"):
                prefix = pattern[:-2]
                result.update(
                    s for s in Scope if s.value.startswith(f"{prefix}:"))
            else:
                try: 
                    result.add(Scope.from_string(pattern))
                except ValueError: 
                    continue
        
        return result
    
    @classmethod
    def has_permission(cls, role: str, required: Scope | set[Scope]) -> bool:
        """Check if role has required scope(s)."""
        role_scopes = cls.get_scopes(role)
        required_set = {required} if isinstance(required, Scope) else required
        return required_set.issubset(role_scopes)
    
    @classmethod
    def add_role(cls, name: str, patterns: set[str]) -> None:
        """Dynamic role creation (e.g., from admin panel)."""
        cls._CONFIG[name] = RoleConfig(name=name, scope_patterns=patterns)