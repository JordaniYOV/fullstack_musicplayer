import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
import sys
import os
import uuid

from datetime import date, datetime, timedelta
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient

from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi import FastAPI
from alembic.config import Config
from alembic import command


TEST_DB_URL = "postgresql+psycopg://postgres:1234@localhost:5431/muse"
# TEST_SYNC_DB_URL = "postgres://test:test@localhost:5433/test_charts"
TEST_REDIS_URL = "redis://localhost:6379"

# @pytest.fixture(scope='session', autouse=True)
# def db() -> Generator[Session, None, None]: 
#     with Session(engine) as session: 
#         yield session

# @pytest.fixture(scope="module")
# def client() -> Generator[TestClient, None, None]: 
#     with TestClient(app) as c: 
#         yield c

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pytest_plugins = ("pytest_asyncio",)

@pytest.fixture(scope="session")
def event_loop(): 
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def async_engine(): 
    """Create async engine for tests"""
    os.environ["ENV"] = 'test'
    engine = create_async_engine(
        TEST_DB_URL, 
        echo=False, 
        future=True, 
        poolclass=StaticPool,
    )

    # try:
    #     alembic_cfg = Config("alembic.ini")
    #     alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    #     command.upgrade(alembic_cfg, "head")
    # except Exception as e:
    #     print(f"Migration error {e}")
    #     raise


    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # async with engine.begin() as conn: 
    #     await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]: 
    """Create async session"""
    async_session = async_sessionmaker(
        async_engine, 
        class_= AsyncSession,
        expire_on_commit=False, 
        autoflush=False, 
        autocommit=False,
    )

    async with async_session() as session: 
        yield session

        await session.rollback()

@pytest.fixture
def sync_engine():
    sync_engine = create_engine(
        TEST_DB_URL, 
        echo=False,
        poolclass=StaticPool
    )
    os.environ["ENV"] = 'test'
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    # SQLModel.metadata.create_all(bind=sync_engine)

    yield sync_engine

    # SQLModel.metadata.drop_all(bind=sync_engine)
    sync_engine.dispose()

@pytest.fixture
def sync_session(sync_engine):
    """Create sync session for celery"""
    sync_session = sessionmaker(bind=sync_engine)

    with sync_session() as session:
        yield session
        session.rollback()

@pytest.fixture
def mock_kafka_producer():
    """
    A mock KafkaProducerService that records calls without hitting a broker.
    send() returns True by default. Override side_effect in individual tests.
    """

    producer = MagicMock()
    producer.send = AsyncMock(return_value=True)
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.is_healthy = True
    producer._consecutive_failures = 0
    producer._circuit_opened_at = None
    return producer

@pytest.fixture
def mock_kafka_consumer():
    """
    A mock KafkaConsumerService.
    """
    consumer = MagicMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.is_healthy = True
    consumer.subscribed_topics = ["play-events"]
    consumer.consume_loop = AsyncMock()
    return consumer
    

@pytest.fixture
async def test_app(async_engine) -> FastAPI:
    """Create test app with override dependecies"""
    from app.main import app

    async def override_get_db():
        async_session = async_sessionmaker(
            async_engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    from app.core.redis import redis
    get_async_redis_orig = redis.get_async_redis

    async def ovveride_get_async_redis(): 
        if redis.async_redis_client is None:
            redis.async_redis_client = redis.aioredis.from_url(
                TEST_REDIS_URL, 
                decode_response=True
            )

        return redis.async_redis_client
    
    redis.get_async_redis = ovveride_get_async_redis

    app.state.kafka_producer = mock_kafka_producer()
    app.state.kafka_consumer = mock_kafka_consumer()
    
    yield app

    app.dependency_overrides.clear()
    redis.get_async_redis = get_async_redis_orig

    try:
        redis_client = await ovveride_get_async_redis()
        await redis_client.flushdb()
        await redis_client.close()
    except Exception:
        pass

@pytest_asyncio.fixture()
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]: 
    """Async client for tests"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client: 
        yield client

@pytest.fixture()
def sync_client(test_app) -> TestClient:
    """Sync client for simple test"""
    return TestClient(test_app)

@pytest_asyncio.fixture(autouse=True)
async def clean_redis(): 
    """Clean redis before each test"""
    try: 
        from app.core.redis.redis import get_async_redis
        redis = await get_async_redis()
        await redis.flushdb()
        yield
        await redis.aclose()
    except:
        yield

@pytest.fixture
def sample_tracks_data(): 
    """Test data """

    return [
        {"title": "Bohemian Rhapsody", "artist": "Queen", "duration_sec": 354, "genre": "Rock"},
        {"title": "Billie Jean", "artist": "Michael Jackson", "duration_sec": 294, "genre": "Pop"},
        {"title": "Smells Like Teen Spirit", "artist": "Nirvana", "duration_sec": 301, "genre": "Grunge"},
        {"title": "Imagine", "artist": "John Lennon", "duration_sec": 183, "genre": "Pop"},
        {"title": "Hotel California", "artist": "Eagles", "duration_sec": 391, "genre": "Rock"},
    ]

@pytest_asyncio.fixture
async def sample_tracks(async_session, sample_tracks_data):
    """Create test tracks in DB"""
    from app.models.tracks import Track

    tracks = []
    for data in sample_tracks_data: 
        track = Track(**data)
        async_session.add(track)
        tracks.append(track)

    await async_session.commit()

    for track in tracks:
        await async_session.refresh(track)

    return tracks

@pytest_asyncio.fixture
async def sample_plays_events(async_session, sample_tracks): 
    """Create test listen event"""
    from app.models.tracks import PlayEvent

    events = []
    base_time = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=12)

    for _ in range(100):
        events.append(PlayEvent(
            track_id=sample_tracks[0].id, 
            user_id=uuid.uuid4(),
            played_at=base_time + timedelta(minutes=1),
            duration_listened=354, 
            completed=1
        ))
    
    for _ in range(80):
        events.append(PlayEvent(
            track_id=sample_tracks[1].id, 
            user_id=uuid.uuid4(), 
            played_at=base_time + timedelta(minutes=1),
            duration_listened=333, 
            completed=1
        ))

    for _ in range(50):
        events.append(PlayEvent(
            track_id=sample_tracks[2].id, 
            user_id=uuid.uuid4(), 
            played_at=base_time + timedelta(minutes=1),
            duration_listened=344, 
            completed=1
        ))

    for event in events:
        async_session.add(event)
    
    await async_session.commit()
    return events

