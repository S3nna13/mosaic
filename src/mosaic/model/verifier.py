"""Verifier head — per-token confidence / stability prediction.

Implements a lightweight linear projection from model hidden states to a
per-token scalar score.  Used by evaluation benchmarks to measure how
confident the model is in its predictions.
"""

from __future__ import annotations

import torch
from torch import nn


class VerifierHead(nn.Module):
    """Linear layer that maps hidden states [B, T, D] → [B, T] scores."""

    def __init__(self, d_model: int):
        super().__init__()
        self.linear = nn.Linear(d_model, 1)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:  # [B, T, D] → [B, T]
        return self.linear(hidden).squeeze(-1)
