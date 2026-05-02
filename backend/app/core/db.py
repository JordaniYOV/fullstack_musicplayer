import platform
import asyncio

from sqlmodel import create_engine

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

async_engine = create_async_engine(
    settings.ASYNC_DB_URL, 
    echo=True, 
    pool_size=5, 
    max_overflow=10, 
    pool_pre_ping=True)

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sync_engine = create_engine(
    settings.ASYNC_DB_URL, 
    echo=True, 
    pool_size=5)


