"""RedSea Router — MLP-based compute-path selector.

Classifies incoming prompts into one of five inference modes:
  • fast        — single pass, low temperature (simple Q&A)
  • deliberate  — chain-of-thought, higher tokens (math / reasoning)
  • search      — retrieve from external tools first (current events, search)
  • agent       — multi-step tool use (coding, complex workflows)
  • memory      — heavy memory consolidation required

The router examines prompt embeddings (mean-pooled last-layer hidden states) and
outputs a categorical mode. In production, this can be a fine-tuned classifier;
here we implement a lightweight heuristic fallback + trainable MLP stub.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import torch
import torch.nn as nn


class InferenceMode(str, Enum):
    FAST        = "fast"
    DELIBERATE  = "deliberate"
    SEARCH      = "search"
    AGENT       = "agent"
    MEMORY      = "memory"


@dataclass
class RouterConfig:
    """Configuration for RedSea Router."""
    mode: InferenceMode = InferenceMode.FAST
    use_heuristic_fallback: bool = True   # if no MLP weights, use keyword rules
    # Feature thresholds for heuristic mode
    math_threshold: float = 0.15   # token overlap with math operators
    code_threshold: float = 0.10   # code symbol density
    tool_threshold: float = 0.20   # mentions of "search", "lookup", etc.
    ambiguity_threshold: float = 0.25  # high entropy in token distribution


class RedSeaRouter(nn.Module):
    """MLP-based mode classifier + heuristic fallback."""
    def __init__(self, dim: int, hidden: int = 64, n_modes: int = 5):
        super().__init__()
        self.dim = dim
        self.n_modes = n_modes
        self.classifier = nn.Sequential(
            nn.Linear(dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, n_modes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, T, dim] mean-pooled over T.
        Returns: logits [B, n_modes]"""
        if x.dim() == 3:
            x = x.mean(dim=1)  # [B, dim]
        return self.classifier(x)

    @torch.no_grad()
    def predict_mode(self, x: torch.Tensor, cfg: RouterConfig) -> InferenceMode:
        logits = self.forward(x)  # [B, 5]
        probs = torch.softmax(logits, dim=-1)
        predicted_idx = torch.argmax(probs, dim=-1).item()
        mode = InferenceMode(["fast", "deliberate", "search", "agent", "memory"][predicted_idx])

        if cfg.use_heuristic_fallback:
            # Simple keyword override for high-confidence cases
            # In real system, text would be passed here; for now, trust MLP
            pass
        return mode


def heuristic_mode_from_text(text: str) -> InferenceMode:
    """Keyword-based quick mode classifier (used when transformer not yet run)."""
    t = text.lower()
    math_syms = set("+-*/=<>∑∫√πΔ")
    code_syms = set("{}[]():;->,.<>")
    words = set(t.split())

    math_score = len(set(t) & math_syms) / max(1, len(t))
    code_score = len(set(t) & code_syms) / max(1, len(t))
    tool_words = {"search", "lookup", "find", "query", "weather", "news"}
    tool_score = len(words & tool_words) / max(1, len(words))

    if tool_score > 0.15:
        return InferenceMode.SEARCH
    if code_score > 0.08:
        return InferenceMode.AGENT
    if math_score > 0.10 or any(w in t for w in ["solve", "calculate", "prove"]):
        return InferenceMode.DELIBERATE
    return InferenceMode.FAST


__all__ = ["InferenceMode", "RedSeaRouter", "RouterConfig", "heuristic_mode_from_text"]
