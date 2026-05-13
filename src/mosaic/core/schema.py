"""Pydantic schemas used throughout MOSAIC."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: Literal["openai", "anthropic", "ollama", "local"] = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    path: str | None = None


class EvalAssertion(BaseModel):
    type: Literal[
        "exact", "contains", "regex", "llm_judge", "factual", "safe", "custom"
    ] = "exact"
    metric: str | None = None
    value: str | None = None
    threshold: float = 0.8


class EvalConfig(BaseModel):
    prompts: list[dict[str, Any]] = Field(default_factory=list)  # [{"template": ...}]
    tests: list[dict[str, Any]] = Field(default_factory=list)  # [{"input", "expected"}]
    assertions: list[EvalAssertion] = Field(default_factory=list)


class GuardConfig(BaseModel):
    rails: list[str] = Field(
        default_factory=lambda: [
            "jailbreak",
            "injection",
            "toxicity",
            "pii",
            "secrets",
            "context",
            "rag_poisoning",
            "structured_output",
            "constitutional",
            "factual",
            "hallucination",
            "output",
            "rate_limit",
        ]
    )
    enabled: bool = True


class MemoryConfig(BaseModel):
    scratch_capacity: int = 512
    episode_capacity: int = 4096
    archive_capacity: int = 8192
    persistence_path: str | None = None


class SecurityConfig(BaseModel):
    rate_limit_max: int = 100
    rate_limit_window_seconds: int = 60
    enable_audit_ledger: bool = True
    redact_pii_in_memory: bool = True


class LimitsConfig(BaseModel):
    rate_limit_max: int = 100
    rate_limit_window_seconds: int = 60


class TrainingConfig(BaseModel):
    epochs: int = 3
    batch_size: int = 8
    gradient_accumulation: int = 4
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    warmup_steps: int = 100
    checkpoint_dir: str = "checkpoints/"
    device: str = "cuda"


try:
    from .config import MosaicConfig as _ModelArchConfig
except ImportError:

    class _ModelArchConfig(BaseModel):
        pass


class AigisConfig(BaseModel):
    """Top-level unified config schema."""

    version: str = "1"
    name: str | None = None
    description: str | None = None
    model: ModelConfig = Field(default_factory=ModelConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)
    guard: GuardConfig = Field(default_factory=GuardConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)


# Type aliases for backwards compatibility
AigisMode = Literal["eval", "guard", "run", "serve", "dashboard"]


__all__ = [
    "AigisConfig",
    "AigisMode",
    "EvalAssertion",
    "EvalConfig",
    "GuardConfig",
    "ModelConfig",
]
