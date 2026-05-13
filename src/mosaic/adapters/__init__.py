"""Adapters — multi-provider LLM orchestration layer."""

from __future__ import annotations


from .anthropic_adapter import AnthropicAdapter
from .base import BaseAdapter, CircuitBreaker, Message, ModelResponse
from .local_adapter import LocalAdapter
from .ollama_adapter import OllamaAdapter
from .openai_adapter import OpenAIAdapter


def build_adapter(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    **kwargs,
) -> BaseAdapter:
    """Factory — instantiate adapter from provider string + arguments."""
    provider = provider.lower()
    if provider == "openai":
        return OpenAIAdapter(api_key=api_key or "env", model=model or "gpt-4o-mini", **kwargs)
    if provider == "anthropic":
        return AnthropicAdapter(api_key=api_key or "env", model=model or "claude-3-5-sonnet-20241022")
    if provider == "ollama":
        return OllamaAdapter(base_url=kwargs.get("host", "http://localhost:11434"), model=model or "llama3.2:3b")
    if provider in ("local", "mosaic"):
        return LocalAdapter(model_path=kwargs.get("path", ""), use_mosaic_transformer=(provider == "mosaic"))
    raise ValueError(f"Unknown provider: {provider}")

__all__ = [
    "AnthropicAdapter",
    "BaseAdapter",
    "CircuitBreaker",
    "LocalAdapter",
    "Message",
    "ModelResponse",
    "OllamaAdapter",
    "OpenAIAdapter",
    "build_adapter",
]
