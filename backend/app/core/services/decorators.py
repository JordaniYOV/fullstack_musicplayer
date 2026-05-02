import functools
import time

from typing import Callable, Any, Optional
# from dataclasses import dataclass
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.logging_config import get_logger

logger = get_logger("app.service.decorators")

# @dataclass
class LogConfig(BaseModel):
    """Log conf for method"""
    operation: str 
    log_args: bool = False
    chart_type: Optional[str] = None

def log_chart_operation(config: LogConfig):
    """decorator to log async chrt methods"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs): 
            log = getattr(self, 'logger', logger)

            chart_date = kwargs.get('chart_date') or (args[0] if args else None)
            limit = kwargs.get('limit') or (args[1] if len(args) > 1 else None)

            context = { 
                "operation": config.operation,
                "chart_type": config.chart_type,
            }
            if chart_date:
                context["chart_date" if config.chart_type == 'daily' else "chart_period"] = (
                    chart_date.isoformat() if hasattr(chart_date, 'isoformat') else str(chart_date)
                )
            if limit:
                context["limit"] = limit
            
            log.info(f"{config.operation}_started", **context)
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                success_context = {
                    **context,
                    "duration_ms": round(duration_ms, 2), 
                }

                if hasattr(result, 'entries'):
                    success_context["track_count"] = len(result.entries)
                if hasattr(result, 'total_plays'):
                    success_context["total_plays"] = result.total_plays
                
                log.info(f"{config.operation}_completed", **success_context)
                return result
                
            except ValueError as e:
                duration_ms = (time.time() - start_time) * 1000
                log.warning(
                    "chart_data_missing",
                    **{**context, "error": str(e), "duration_ms": round(duration_ms, 2)}
                )
                from app.models.tracks import ChartResponse
                return ChartResponse(
                    chart_type=config.chart_type,
                    period=str(chart_date) if chart_date else "",
                    entries=[],
                    total_plays=0,
                )
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log.error(
                    f"{config.operation}_failed",
                    **{
                        **context,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "exc_info": True,
                    }
                )
                raise
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs): 
            log = getattr(self, 'logger', logger)

            chart_date = kwargs.get('chart_date') or (args[0] if args else None)
            limit = kwargs.get('limit') or (args[1] if len(args) > 1 else None)

            context = { 
                "operation": config.operation, 
                "chart_type": config.chart_type,
            }
            if chart_date:
                context["chart_date" if config.chart_type == "daily" else "chart_period"] = (
                    chart_date.isoformat() if hasattr(chart_date, 'isoformat') else str(chart_date)
                ) 
            if limit:
                context["limit"] = limit
            
            log.info(f"{config.operation}_started", **context)
            start_time = time.time()

            try:
                result = func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                success_context = {
                    **context,
                    "duration_ms": round(duration_ms, 2)
                }
                if isinstance(result, dict): 
                    success_context["track_count"] = len(result.get("entries", []))

                    success_context["total_plays"] = result.get("total_plays", 0)

                log.info(f"{config.operation}_completed", **success_context)
                return result

            except ValueError as e:
                duration_ms = (time.time() - start_time) * 1000
                log.warning(
                    "sync_chart_empty", 
                    **{**context, "error": str(e), "duration_ms": round(duration_ms, 2)}
                )
                return {"entries": [], "total_plays": 0}
            
            except SQLAlchemyError as e:
                duration_ms = (time.time() - start_time) * 1000
                log.error(
                    f"{config.operation}_db_error", 
                    **{
                        **context, 
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                )
                raise

            except Exception as e:
                duration_ms = (time.time() -  start_time) * 1000
                log.error(
                    f"{config.operation}_failed",
                    **{
                        **context,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e), 
                        "exc_info": True,
                    }
                )
                raise 
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator