from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from loguru import logger as _loguru_logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        _loguru_logger.bind(logger="std").opt(depth=6, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
    _loguru_logger.remove()
    _loguru_logger.add(sys.stdout, serialize=True, backtrace=False, diagnose=False)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str = "app") -> Any:
    return structlog.get_logger(name)

