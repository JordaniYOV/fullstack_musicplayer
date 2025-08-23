import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = secrets.token_urlsafe(32)

    DB_URL: str = f"sqlite:///./backend/app/core/database.db"


settings = Settings()