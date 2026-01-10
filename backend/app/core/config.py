import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


    # API_V1_STR: str = "/api/v1"
    DB_URL: str = f"postgresql://postgres:0508@localhost:5432/music"


settings = Settings()