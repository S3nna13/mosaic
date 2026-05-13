"""Structured logging — JSON lines with context.

Integrates with structlog in production, falls back to stdlib if unavailable.
All MOSAIC components import `get_logger()` instead of using stdlib logging directly.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

try:
    import structlog

    _structlog_available = True
except ImportError:
    _structlog_available = False


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_logger(name: str = "mosaic"):
    """Return a structured logger — structlog if installed, else stdlib JSON."""
    if _structlog_available:
        return structlog.get_logger(name)
    # Stdlib fallback — each log call emits a JSON line
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# Convenience wrappers
def log_event(level: str, event: str, **kwargs):
    """Structured event logging."""
    logger = get_logger()
    if _structlog_available:
        method = getattr(logger, level)
        method(event, **kwargs)
    else:
        payload = {"event": event, "ts": datetime.now(UTC).isoformat(), **kwargs}
        logger.log(
            logging.getLevelName(level.upper()),
            json.dumps(payload, default=_json_default),
        )


def log_request(method: str, path: str, status: int, duration_ms: float, **extra):
    print(
        json.dumps(
            {
                "event": "http_request",
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
                **extra,
            }
        )
    )


def log_guardrail_hit(name: str, severity: str, score: float, **extra):
    print(
        json.dumps(
            {
                "event": "guardrail_hit",
                "rail": name,
                "severity": severity,
                "score": score,
                **extra,
            }
        )
    )


def log_tool_call(tool: str, success: bool, duration_ms: float, **extra):
    print(
        json.dumps(
            {
                "event": "tool_call",
                "tool": tool,
                "success": success,
                "duration_ms": duration_ms,
                **extra,
            }
        )
    )
