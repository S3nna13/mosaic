"""Adapters — multi-provider LLM orchestration layer."""

from __future__ import annotations

from typing import Optional

from .base import BaseAdapter, Message, ModelResponse, CircuitBreaker
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .ollama_adapter import OllamaAdapter
from .local_adapter import LocalAdapter


def build_adapter(
    provider: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseAdapter:
    """Factory — instantiate adapter from provider string + arguments."""
    provider = provider.lower()
    if provider == "openai":
        return OpenAIAdapter(api_key=api_key or "env", model=model or "gpt-4o-mini", **kwargs)
    elif provider == "anthropic":
        return AnthropicAdapter(api_key=api_key or "env", model=model or "claude-3-5-sonnet-20241022")
    elif provider == "ollama":
        return OllamaAdapter(base_url=kwargs.get("host", "http://localhost:11434"), model=model or "llama3.2:3b")
    elif provider in ("local", "mosaic"):
        return LocalAdapter(model_path=kwargs.get("path", ""), use_mosaic_transformer=(provider == "mosaic"))
    else:
        raise ValueError(f"Unknown provider: {provider}")

__all__ = [
    "BaseAdapter", "Message", "ModelResponse", "CircuitBreaker",
    "OpenAIAdapter", "AnthropicAdapter", "OllamaAdapter", "LocalAdapter",
    "build_adapter",
]
