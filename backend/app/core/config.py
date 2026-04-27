import secrets
import picologging as logging
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Muse"

    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis
    redis_url: str = "redis://localhost:12345"
    redis_host: str = "localhost"
    redis_port: int = 12345
    redis_password: Optional[str] = None
    redis_max_connections: int = 10
    redis_timeout: int = 5
    redis_decode_response: bool = True
    cache_ttl: int = 3600

    API_V1_STR: str = "/api/v1"
    # DB_URL: str = f"postgresql+asyncpg://postgres:0508@localhost:5432/music"
    # ASYNC_DB_URL: str = f"postgresql+asyncpg://postgres:1234@localhost:1234/muse"
    ASYNC_DB_URL: str = f"postgresql+psycopg://postgres:1234@localhost:1234/muse"

    LOGGER: logging.basicConfig = logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s-%(name)s-%(levelname)s-%(message)s"
    )


settings = Settings()