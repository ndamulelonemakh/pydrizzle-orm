from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import TextIO

LOG_LEVEL_ENV = "PYDRIZZLE_LOG_LEVEL"
LOG_FORMAT_ENV = "PYDRIZZLE_LOG_FORMAT"

_DEFAULT_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _DEFAULT_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"[{record.levelname}] {record.getMessage()}"
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key not in _DEFAULT_ATTRS and not key.startswith("_"):
                extras.append(f"{key}={value}")
        if extras:
            return f"{base} | {' '.join(extras)}"
        return base


def configure_logging(
    *,
    level: str | None = None,
    fmt: str | None = None,
    stream: TextIO | None = None,
    force: bool = False,
) -> None:
    logger = logging.getLogger("pydrizzle")

    if logger.handlers and not force:
        return

    resolved_level = (level or os.getenv(LOG_LEVEL_ENV, "INFO")).upper()
    resolved_fmt = (fmt or os.getenv(LOG_FORMAT_ENV, "text")).lower()
    numeric_level = getattr(logging, resolved_level, logging.INFO)

    handler = logging.StreamHandler(stream or sys.stderr)
    if resolved_fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())

    logger.handlers.clear()
    logger.setLevel(numeric_level)
    logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    base = "pydrizzle"
    if name:
        return logging.getLogger(f"{base}.{name}")
    return logging.getLogger(base)
