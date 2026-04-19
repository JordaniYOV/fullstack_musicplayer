from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.main import api_router
from app.core.redis.redis import get_async_redis, get_sync_redis, close_async_redis, close_sync_redis

import sys 
import asyncio
import picologging as logging
from picologging.handlers import RotatingFileHandler

def setup_logger(): 
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    format = '%(asctime)s-%(name)s-%(levelname)s-%(message)s'

    root_logger.addHandler(logging.StreamHandler(sys.stdout))
    root_logger.handlers[0].setFormatter(logging.Formatter(format))

    file_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(format))
    root_logger.addHandler(file_handler)

setup_logger()

@asynccontextmanager
async def async_redis(app: FastAPI): 
    print('Starting async redis')
    app.state.async_redis = await get_async_redis()
    yield
    print('Shuting down async redis')
    await close_async_redis()

@contextmanager
def sync_redis(app: FastAPI):
    print('Starting sync redis')
    app.state.sync_redis = get_sync_redis()
    yield
    print('Shuting down sync redis')
    close_sync_redis()

@asynccontextmanager
async def combined_lifespan(app: FastAPI): 
    """
    Merge async and syn redis contexts
    """
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(async_redis(app))

        stack.enter_context(sync_redis(app))

        print('All services is working')
        yield 
        print('Shutitng down all services')

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(
    title=settings.PROJECT_NAME, 
    lifespan=combined_lifespan,
)

origins = [
    "http://localhost:6000", 
    "http://localhost:5173",
    
]

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)


app.include_router(api_router)