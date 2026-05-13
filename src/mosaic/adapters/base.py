"""Base adapter — all provider implementations derive from this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mosaic.multimodal.vision import ImageInput


@dataclass
class Message:
    role: str          # "user" | "assistant" | "system"
    content: str
    images: list[ImageInput] | None = None


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: dict[str, int]
    raw: dict[str, Any] | None = None


class BaseAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def chat(self, messages: list[Message], **kwargs) -> ModelResponse:
        ...

    def list_models(self) -> list[str]:
        return []

    def health(self) -> bool:
        return True


class CircuitBreaker:
    """Simple CB: allow N failures within window, then open for recovery-time."""
    def __init__(self, max_failures: int = 3, recovery_timeout: float = 30.0):
        self.max_failures = max_failures
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure = 0.0
        self.state: str = "closed"  # closed | open | half-open

    def call(self, fn):
        import time
        if self.state == "open":
            if time.time() - self.last_failure > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise RuntimeError("Circuit breaker open — backend unavailable")

        try:
            result = fn()
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.max_failures:
                self.state = "open"
            raise e
        else:
            self.failures = 0
            return result
