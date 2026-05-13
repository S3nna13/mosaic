"""MOSAIC model architecture configuration.

Combines Moses memory-first specs with additional features:
- 1.6B base parameters (extensible to 3B)
- Grouped Query Attention (GQA) for memory efficiency
- Optional RoPE scaling (dynamic NTK-aware)
- Support for memory cross-attention (every N layers)
- Register token configurations
- Tool head and verifier head toggles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MosaicConfig:
    """Configuration for the MOSAIC model architecture.

    Attributes:
        n_params: Total parameter count (approximate, for logging/metadata)
        n_layers: Number of transformer blocks
        d_model: Model hidden dimension
        n_heads: Number of attention heads (query)
        n_kv_heads: Number of key-value heads (for GQA)
        d_ff: Feed-forward inner dimension (typically 4x d_model for SwiGLU)
        vocab_size: Token vocabulary size
        context_len: Maximum sequence length
        rope_theta: Base frequency for rotary position embeddings
        rope_scaling: If set, apply scaling factor for longer contexts
        hidden_act: Activation function (silu, gelu, relu)
        rms_norm_eps: Epsilon for RMSNorm
        initializer_range: Std dev for weight initialization
        tie_word_embeddings: Share input/output embeddings
        use_cache: Enable KV caching during generation
        use_memory_cross_attn: Include cross-attention to memory tiers
        memory_cross_attn_interval: Inject memory cross-attn every N layers
        use_register_tokens: Enable Sinai Register tokens
        n_registers: Number of learnable register tokens (default 16)
        use_adaptive_compute: Enable Red Sea Router for dynamic path selection
        use_verifier_head: Train secondary head for output stability scoring
        use_tool_head: Enable tool use prediction head
        tool_head_top_k: Max concurrent tools to predict (default 3)
        memory_tiers: Ordered list of memory tier names
        special_tokens: Mapping of token name → ID (from tokenizer)
    """

    # ── Architecture ──────────────────────────────────────────────────────────
    n_params: float = 1.6e9
    n_layers: int = 24
    d_model: int = 2048
    n_heads: int = 16
    n_kv_heads: int = 8
    d_ff: int = 5632  # ~2.67x d_model for SwiGLU (2x for standard MLP)
    vocab_size: int = 128_000
    context_len: int = 8192
    rope_theta: float = 500_000.0
    rope_scaling: dict | None = None  # e.g. {"type":"dynamic","factor":2.0}
    hidden_act: Literal["silu", "gelu", "relu"] = "silu"
    rms_norm_eps: float = 1e-6
    initializer_range: float = 0.02
    tie_word_embeddings: bool = True
    use_cache: bool = True

    # ── Memory System ─────────────────────────────────────────────────────────
    use_memory_cross_attn: bool = True
    memory_cross_attn_interval: int = 4  # every Nth layer
    use_register_tokens: bool = True
    n_registers: int = 16
    memory_tiers: list[str] = field(
        default_factory=lambda: ["scratch", "episode", "archive"]
    )
    scratch_capacity: int = 512
    episode_capacity: int = 4_096
    archive_capacity: int = 8_192

    # ── Agentic / Tool Use ────────────────────────────────────────────────────
    use_adaptive_compute: bool = True
    use_verifier_head: bool = True
    use_tool_head: bool = True
    tool_head_top_k: int = 3

    # ── Special Tokens ────────────────────────────────────────────────────────
    # Filled at runtime from tokenizer; defaults here are informative only.
    special_tokens: dict[str, int] = field(
        default_factory=lambda: {
            "pad_token": 0,
            "eos_token": 1,
            "bos_token": 2,
            "system": 3,
            "user": 4,
            "assistant": 5,
            "memory_scratch": 6,
            "memory_episode": 7,
            "memory_archive": 8,
            "register": 9,
            "tool_call": 10,
            "tool_response": 11,
            "verifier_accept": 12,
            "verifier_reject": 13,
            "covenant": 14,
            "ark_entry": 15,
            "manna": 16,
            "red_sea_route": 17,
            "red_sea_default": 18,
            "staff_stable": 19,
            "staff_uncertain": 20,
            "thinking_start": 21,
            "thinking_end": 22,
            "lineage": 23,
        }
    )

    def __post_init__(self) -> None:
        """Validate invariants after construction."""
        if self.n_kv_heads > self.n_heads:
            raise ValueError("n_kv_heads cannot exceed n_heads")
        if self.n_heads % self.n_kv_heads != 0:
            raise ValueError("n_heads must be divisible by n_kv_heads")
        if self.memory_cross_attn_interval <= 0:
            raise ValueError("memory_cross_attn_interval must be positive")
        if self.n_registers <= 0:
            raise ValueError("n_registers must be positive")

    @property
    def head_dim(self) -> int:
        """Dimension per attention head."""
        return self.d_model // self.n_heads

    @property
    def ffn_dim(self) -> int:
        """Inner dimension of the feed-forward network."""
        return self.d_ff

    @property
    def n_query_groups(self) -> int:
        """Number of groups in GQA (n_heads // n_kv_heads)."""
        return self.n_heads // self.n_kv_heads

    def to_dict(self) -> dict:
        """Serialize to a plain dict (useful for JSON/YAML)."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data: dict) -> MosaicConfig:
        """Deserialize from a plain dict."""
        return cls(**data)
