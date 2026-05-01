import logging
import sys
from typing import Any, Dict

import structlog

def configure_logging(debug: bool = False): 
    """
    structlog and logging settings
    -dev: color output
    -prod: JSON  for ELK
    """

    shared_proccessors: list = [
        structlog.processors.TimeStamper(fmt="iso" if not debug else None), 

        structlog.stdlib.add_logger_name, 

        structlog.stdlib.add_log_level, 
        structlog.processors.format_exc_info, 
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME, 
                structlog.processors.CallsiteParameter.FUNC_NAME, 
                structlog.processors.CallsiteParameter.LINENO, 
            }
        ), 
        structlog.stdlib.ExtraAdder(),
    ]

    if debug:
        structlog.configure(
            processors=shared_proccessors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.DEBUG
            ), 
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=shared_proccessors + [
                structlog.processors.dict_tracebacks, 
                structlog.processors.JSONRenderer(), 
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO), 
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(), 
            cache_logger_on_first_use=True,
        )

    logging.basicConfig(
        format="%(message)s", 
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True)
        if debug else structlog.processors.JSONRenderer(), 
         foreign_pre_chain=shared_proccessors, )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not debug else logging.DEBUG)


def get_logger(name: str, **context: Any) -> structlog.stdlib.BoundLogger:
    """get logger with context bound"""

    return structlog.get_logger(name).bind(**context)

