"""Structured logging helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    processors = [
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        structlog.processors.add_log_level,
        (
            structlog.processors.JSONRenderer()
            if json_format
            else structlog.dev.ConsoleRenderer()
        ),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def log_event(event: str, **kwargs: Any) -> None:
    """Emit a structured log line."""
    logger.info(event, **kwargs)


def log_audit(action: str, user: str | None = None, **extra) -> None:
    """Emit an audit-grade event (structured + timestamped)."""
    logger.info(
        "audit", action=action, user=user, ts=datetime.now(UTC).isoformat(), **extra
    )


__all__ = [
    "configure_logging",
    "log_audit",
    "log_event",
    "logger",
]
