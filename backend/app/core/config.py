import secrets
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    # Project
    PROJECT_NAME: str = "Muse"
    DEBUG: bool = False
    ENV: str = "development"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database (deriver psycopg3 can work async and sync)
    # DB_URL: str = f"postgresql+asyncpg://postgres:0508@localhost:5432/music"
    # ASYNC_DB_URL: str = f"postgresql+asyncpg://postgres:1234@localhost:1234/muse"
    ASYNC_DB_URL: str = f"postgresql+psycopg://postgres:1234@localhost:1234/muse"

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_max_connections: int = 10
    redis_timeout: int = 5
    redis_decode_response: bool = True
    cache_ttl: int = 3600

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_consumer_group: str = "muse-backend"
    kafka_startup_timeout: int = 30

    # Router
    API_V1_STR: str = "/api/v1"
   


settings = Settings()