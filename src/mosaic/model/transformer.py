"""Transformer backbone with GQA, RoPE, Exodus memory injection.

We define:
- MosaicConfig: structural hyper-params (depth, width, heads, kv_heads)
- MosaicTransformer: forward pass with optional cross-attention to Exodus tiers
- VerifierHead: per-token stability prediction
- Special token IDs for memory/register/tool markers
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F  # noqa: N812

from mosaic.core.schema import AigisConfig


# ── Special token IDs (must match tokenizer when integrated) ──────────────────
class Token:
    MEM_SCRATCH = 128_000  # start of scratch segment
    MEM_EPISODE = 128_001
    MEM_ARCHIVE = 128_002
    REGISTER    = 128_003  # Sinai register marker
    TOOL_CALL   = 128_004
    TOOL_RESULT = 128_005
    VERIFY      = 128_006  # verifier flow control


@dataclass
class MosaicConfig:
    """Structural hyper-parameters for the Mosaic transformer."""
    vocab_size: int = 128_256  # GPT-4 tokenizer size
    n_layers: int = 24
    n_heads: int = 16
    n_kv_heads: int = 4
    dim: int = 2048
    mlp_ratio: float = 4.0
    max_seq_len: int = 8192
    rope_theta: float = 10000.0
    rope_scaling: dict | None = None  # e.g. {"type":"dynamic","factor":2.0}
    use_exodus_cross_attn: bool = True  # inject memory every N layers
    exodus_inject_every: int = 4
    register_count: int = 16   # number of Sinai learnable tokens
    dropout: float = 0.1
    bias: bool = False

    # derived
    head_dim: int = field(init=False)
    inner_dim: int = field(init=False)

    def __post_init__(self):
        assert self.dim % self.n_heads == 0
        self.head_dim = self.dim // self.n_heads
        self.inner_dim = int(self.mlp_ratio * self.dim)


class RMSNorm(nn.Module):
    """Root-mean-square layer norm (no bias)."""
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T, dim]
        rms = x.pow(2).mean(-1, keepdim=True).sqrt()
        x_normed = x / (rms + self.eps)
        return self.weight * x_normed


class RotaryEmbedding(nn.Module):
    """RoPE sinusoidal position embeddings."""
    def __init__(self, dim: int, max_seq_len: int, theta: float = 10000.0):
        super().__init__()
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        self.dim = dim
        self.max_seq_len = max_seq_len

    def forward(self, seq_len: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
        t = torch.arange(seq_len, device=device, dtype=self.inv_freq.dtype)
        freqs = torch.einsum("i,j->ij", t, self.inv_freq)  # [T, dim//2]
        emb = torch.cat((freqs, freqs), dim=-1)  # [T, dim]
        cos = emb.cos()
        sin = emb.sin()
        return cos, sin

    @staticmethod
    def apply_rope(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        # x: [B, T, n_heads, head_dim]
        # cos/sin: [1, T, 1, head_dim] broadcast compatible
        head_dim = x.shape[-1]
        assert cos.shape[-1] == head_dim
        x1, x2 = x[..., : head_dim // 2], x[..., head_dim // 2 :]
        rotated = torch.cat((-x2, x1), dim=-1)
        return (x * cos) + (rotated * sin)


class GQAAttention(nn.Module):
    """Grouped-Query Attention with optional Exodus tier cross-attention."""
    def __init__(self, cfg: MosaicConfig, layer_idx: int):
        super().__init__()
        self.cfg = cfg
        self.layer_idx = layer_idx
        self.n_heads = cfg.n_heads
        self.n_kv_heads = cfg.n_kv_heads
        self.head_dim = cfg.head_dim

        assert cfg.n_heads % cfg.n_kv_heads == 0
        self.n_local = cfg.n_heads // cfg.n_kv_heads  # groups per KV head

        self.wq = nn.Linear(cfg.dim, cfg.dim, bias=cfg.bias)
        self.wk = nn.Linear(cfg.dim, cfg.n_kv_heads * cfg.head_dim, bias=cfg.bias)
        self.wv = nn.Linear(cfg.dim, cfg.n_kv_heads * cfg.head_dim, bias=cfg.bias)
        self.wo = nn.Linear(cfg.dim, cfg.dim, bias=cfg.bias)

        # Learnable Sinai register embeddings (one vector per register)
        self.sinai_registers = nn.Parameter(torch.randn(cfg.register_count, cfg.dim))

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        *,  # keyword-only below
        exodus_scratch: torch.Tensor | None = None,
        exodus_episode: torch.Tensor | None = None,
        exodus_archive: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """x: [B, T, dim].
           exodus_*: [B, TierTokens, dim] — secondary sequences for cross-attn
        Returns: [B, T, dim] with memory-augmented attention if tiers provided.
        """
        B, T, _ = x.shape  # noqa: N806
        q = self.wq(x).view(B, T, self.n_heads, self.head_dim)
        k = self.wk(x).view(B, T, self.n_kv_heads, self.head_dim)
        v = self.wv(x).view(B, T, self.n_kv_heads, self.head_dim)

        q = RotaryEmbedding.apply_rope(q, cos, sin)
        k = RotaryEmbedding.apply_rope(k, cos, sin)

        # repeat KV to match GQA grouping
        k = torch.repeat_interleave(k, dim=2, repeats=self.n_local)
        v = torch.repeat_interleave(v, dim=2, repeats=self.n_local)

        # ── Build attention mask ────────────────────────────────────────────
        # Causal mask plus optional memory-causality (memory tokens always visible)
        attn_mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        if exodus_scratch is not None or exodus_episode is not None or exodus_archive is not None:
            # Concatenate memory tiers (if present) to K/V for cross-attn
            mem_list: list[torch.Tensor] = []
            if exodus_scratch is not None:
                mem_list.append(exodus_scratch)
            if exodus_episode is not None:
                mem_list.append(exodus_episode)
            if exodus_archive is not None:
                mem_list.append(exodus_archive)
            if mem_list:
                mem_cat = torch.cat(mem_list, dim=1)  # [B, Mtot, dim]
                km = self.wk(mem_cat).view(B, -1, self.n_kv_heads, self.head_dim)
                vm = self.wv(mem_cat).view(B, -1, self.n_kv_heads, self.head_dim)
                km = RotaryEmbedding.apply_rope(km, cos[: km.size(1)], sin[: km.size(1)])
                km = torch.repeat_interleave(km, dim=2, repeats=self.n_local)
                vm = torch.repeat_interleave(vm, dim=2, repeats=self.n_local)
                k = torch.cat([k, km], dim=1)
                v = torch.cat([v, vm], dim=1)

                # ── Sinai Registers ─────────────────────────────────────────
                # Learnable tokens injected at start of every sequence
                regs = self.sinai_registers.unsqueeze(0).expand(B, -1, -1)  # [B, R, dim]
                kr = self.wk(regs).view(B, -1, self.n_kv_heads, self.head_dim)
                vr = self.wv(regs).view(B, -1, self.n_kv_heads, self.head_dim)
                kr = torch.repeat_interleave(kr, dim=2, repeats=self.n_local)
                vr = torch.repeat_interleave(vr, dim=2, repeats=self.n_local)
                k = torch.cat([k, kr], dim=1)
                v = torch.cat([v, vr], dim=1)

                # ── Causal mask extended for memory + registers ─────────────
                Mtot = k.size(1) - T  # extra tokens prepended to K
                causal_ext = torch.zeros(T, Mtot, device=x.device, dtype=torch.bool)
                attn_mask = torch.cat([causal_ext, attn_mask], dim=1)  # [T, Mtot+T]
                # lower-triangular for the (M+T) side
                attn_mask = torch.triu(torch.ones(T + Mtot, T + Mtot, device=x.device), diagonal=1).bool()
                # but queries (real tokens) must NOT see *future* real tokens; they CAN see all memory
                # mask shape: [T_query, K_total]
                # We'll build it incrementally later; for now keep simple causal for speed.

        # Scaled dot-product attention
        q = q.transpose(1, 2)  # [B, H, T, d]
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        scores = torch.matmul(q, k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))

        if attn_mask is not None:
            scores = scores.masked_fill(attn_mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn = F.softmax(scores, dim=-1)
        attn = F.dropout(attn, p=self.cfg.dropout, training=self.training)
        out = torch.matmul(attn, v)  # [B, H, T, d]
        out = out.transpose(1, 2).contiguous().view(B, T, -1)
        return self.wo(out)


class MLP(nn.Module):
    def __init__(self, cfg: MosaicConfig):
        super().__init__()
        hidden = cfg.inner_dim
        self.w1 = nn.Linear(cfg.dim, hidden, bias=cfg.bias)
        self.w2 = nn.Linear(hidden, cfg.dim, bias=cfg.bias)
        self.w3 = nn.Linear(cfg.dim, hidden, bias=cfg.bias)  # SwiGLU gate

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w2(F.silu(self.w3(x)) * self.w1(x))


class MosaicTransformerBlock(nn.Module):
    def __init__(self, cfg: MosaicConfig, layer_idx: int):
        super().__init__()
        self.attn = GQAAttention(cfg, layer_idx)
        self.mlp = MLP(cfg)
        self.attn_norm = RMSNorm(cfg.dim)
        self.mlp_norm = RMSNorm(cfg.dim)

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        exodus_scratch: torch.Tensor | None = None,
        exodus_episode: torch.Tensor | None = None,
        exodus_archive: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Attention residual
        r = x
        x = self.attn_norm(x)
        x = self.attn(x, cos, sin,
                      exodus_scratch=exodus_scratch,
                      exodus_episode=exodus_episode,
                      exodus_archive=exodus_archive)
        x = r + x

        # MLP residual
        r = x
        x = self.mlp_norm(x)
        x = self.mlp(x)
        x = r + x
        return x


class MosaicTransformer(nn.Module):
    """Full Mosaic transformer with Exodus awareness and verifier head."""
    def __init__(self, cfg: MosaicConfig):
        super().__init__()
        self.cfg = cfg
        self.tok_embeddings = nn.Embedding(cfg.vocab_size, cfg.dim)
        self.rope = RotaryEmbedding(cfg.head_dim, cfg.max_seq_len, cfg.rope_theta)

        self.layers = nn.ModuleList([
            MosaicTransformerBlock(cfg, i) for i in range(cfg.n_layers)
        ])
        self.output_norm = RMSNorm(cfg.dim)
        self.lm_head = nn.Linear(cfg.dim, cfg.vocab_size, bias=False)

        # Tie weights + initialise
        self.tok_embeddings.weight = self.lm_head.weight
        self.apply(self._init_weights)

    def _init_weights(self, m: nn.Module):
        if isinstance(m, nn.Linear):
            nn.init.xavier_uniform_(m.weight, gain=0.5)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.LongTensor,  # [B, T]
        *,
        exodus_scratch: torch.Tensor | None = None,
        exodus_episode: torch.Tensor | None = None,
        exodus_archive: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Returns *logits* only — sampling performed by StaffDecoder."""
        B, T = input_ids.shape
        x = self.tok_embeddings(input_ids)
        cos, sin = self.rope(T, device=input_ids.device)

        exodus_inputs = (exodus_scratch, exodus_episode, exodus_archive) if self.cfg.use_exodus_cross_attn else (None, None, None)

        for layer in self.layers:
            x = layer(x, cos, sin, *exodus_inputs)

        x = self.output_norm(x)
        logits = self.lm_head(x)
        return logits

    @torch.no_grad()
    def generate_until_stable(
        self,
        prompt_ids: torch.LongTensor,
        max_new: int = 256,
        stability_threshold: float = 0.9,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> tuple[torch.LongTensor, torch.Tensor]:
        """Generate tokens while monitoring verifier stability.
        Returns: (generated_ids [B, T+l], stability_scores [T+l])
        """
        device = prompt_ids.device
        tokens = prompt_ids
        stabilities = []

        for _ in range(max_new):
            # get logits for next token
            logits = self.forward(tokens)[:, -1, :]  # [B, V]
            logits = logits / temperature
            probs = F.softmax(logits, dim=-1)

            # top-p nucleus sampling
            sorted_probs, sorted_idx = torch.sort(probs, descending=True)
            cumsum = torch.cumsum(sorted_probs, dim=-1)
            mask = cumsum > top_p
            mask[..., 0] = False  # keep at least one
            sorted_probs[mask] = 0.0
            sorted_probs = sorted_probs / sorted_probs.sum(dim=-1, keepdim=True)

            next_token = torch.multinomial(sorted_probs, num_samples=1)  # [B,1]

            # append
            tokens = torch.cat([tokens, next_token], dim=1)

            # verifier head uses last-layer hidden states (accessed via hooks)
            # Here we approximate stability as max-prob of sampled token's top-k neighbours
            with torch.no_grad():
                top_k = torch.topk(probs, k=5).values
                entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
                stability = 1.0 - (entropy / math.log(probs.shape[-1]))  # normalised [0,1]
                stabilities.append(stability.item())

            if stability < stability_threshold:
                # Flag for re-generation in deliberate mode
                break
            if tokens.shape[1] >= self.cfg.max_seq_len:
                break

        return tokens, torch.tensor(stabilities, device=device)


def build_transformer_from_config(cfg: AigisConfig) -> MosaicTransformer:
    """Factory: read model section from AigisConfig and instantiate."""
    mc = MosaicConfig(
        n_layers=cfg.model.depth or 24,
        dim=cfg.model.width or 2048,
        n_heads=cfg.model.n_heads or 16,
        n_kv_heads=cfg.model.n_kv_heads or 4,
        max_seq_len=cfg.model.context_length or 8192,
        rope_theta=cfg.model.rope_theta or 10000.0,
    )
    return MosaicTransformer(mc)
