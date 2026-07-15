from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middlewares.logging import LoggingMiddleware
from app.core.middlewares.rate_limiting import LimitMiddleware
from app.core.errors import (
    AppError, UnauthorizedError, NotFoundError,
    ForbiddenError, ValidationError
)

from .core.config import settings
from .api import all_routes
from app.core.redis.redis import get_async_redis, get_sync_redis, close_async_redis, close_sync_redis
from app.core.kafka.topics import auto_create_topics
from app.core.kafka.producer import KafkaProducerService
from app.core.kafka.consumer import KafkaConsumerService
from app.core.kafka.handlers import handle_play_event
from app.core.kafka.topics import TOPIC_PLAY_EVENTS
from app.logging_config import get_logger


import sys
import asyncio

logger = get_logger('app.main')

@asynccontextmanager
async def async_redis(app: FastAPI): 
    print('Starting async redis')
    logger.info("starting_async_redis")
    app.state.async_redis = await get_async_redis()
    yield
    logger.info("shutting_down_async_redis")
    print('Shuting down async redis')
    await close_async_redis()

@contextmanager
def sync_redis(app: FastAPI):
    print('Starting sync redis')
    logger.info("starting_sync_redis")
    app.state.sync_redis = get_sync_redis()
    yield
    logger.info("shutting_down_sync_redis")
    print('Shuting down sync redis')
    close_sync_redis()

@asynccontextmanager
async def kafka(app: FastAPI):
    # Kafka topics 
    await auto_create_topics()
 
    # Kafka producer 
    producer = KafkaProducerService()
    await producer.start()
    app.state.kafka_producer = producer
 
    # Also update the module-level reference used by Celery tasks
    import app.core.kafka.producer as _producer_module
    _producer_module.kafka_producer = producer
 
    # Kafka consumer
    consumer_service = KafkaConsumerService()
    consumer_service.register_handler(TOPIC_PLAY_EVENTS, handle_play_event)
    await consumer_service.start()
    app.state.kafka_consumer = consumer_service
 
    import app.core.kafka.consumer as _consumer_module
    _consumer_module.kafka_consumer_service = consumer_service
 
    # Start the consumption loop as a background task
    consume_task = asyncio.create_task(
        consumer_service.consume_loop(),
        name="kafka-consumer-loop",
    )
    logger.info("kafka_consumer_loop_started")
 
    logger.info("application_ready", extra={"project": settings.PROJECT_NAME})
 
    # Yield — application is running 
    yield
 
    # Shutdown
    logger.info("application_shutting_down")
 
    consume_task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(consume_task), timeout=10.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
 
    await consumer_service.stop()
    await producer.stop()

    logger.info("application_stopped")

@asynccontextmanager
async def combined_lifespan(app: FastAPI): 
    """
    Merge async and sync redis contexts
    """
    logger.info(
        "application_starting",
        extra={"project": settings.PROJECT_NAME, "env": settings.ENV},
    )
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(async_redis(app))

        stack.enter_context(sync_redis(app))

        await stack.enter_async_context(kafka(app))
        print('All services is working')
        yield 
        print('Shutitng down all services')

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

app.add_middleware(LimitMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(all_routes)

# Exception handlers
@app.exception_handler(AppError)
async def app_exception_handler(request: Request, exc: AppError):
    """Handler для всех AppError"""
    logger.error(
        "app_exception",
        extra={
            "trace_id": getattr(request.state, "trace_id", None),
            "exception": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "errors": exc.details
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler для HTTPException"""
    logger.warning(
        "http_exception",
        extra={
            "trace_id": getattr(request.state, "trace_id", None),
            "status_code": exc.status_code,
            "detail": exc.detail
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler для валидационных ошибок Pydantic"""
    errors = [
        {
            "field": err["loc"][1] if len(err["loc"]) > 1 else "body",
            "message": err["msg"],
            "type": err["type"]
        }
        for err in exc.errors()
    ]

    logger.warning(
        "validation_error",
        extra={
            "trace_id": getattr(request.state, "trace_id", None),
            "errors": errors
        }
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler для всех остальных исключений"""
    logger.error(
        "general_exception",
        extra={
            "trace_id": getattr(request.state, "trace_id", None),
            "exception": type(exc).__name__,
            "message": str(exc)
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "trace_id": getattr(request.state, "trace_id", None)
        }
    )


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
