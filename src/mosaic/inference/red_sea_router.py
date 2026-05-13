"""Red Sea Router — MLP-based adaptive compute path selection router."""

from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class RedSeaRouter(nn.Module):
    """Lightweight MLP router that predicts which compute path to take.

    Paths:
    - 0: standard (regular forward pass)
    - 1: reasoning-heavy (activate deeper analytical layers)
    - 2: memory-intensive (heavy cross-attention to registers/memory)
    - 3: tool-use (enable function-calling layers)
    """

    def __init__(self, d_model: int, n_paths: int = 4, hidden_dim: int = 64):
        super().__init__()
        self.d_model = d_model
        self.n_paths = n_paths
        # Router MLP: take mean-pooled hidden states, output path logits
        self.mlp = nn.Sequential(
            nn.Linear(d_model, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, n_paths),
        )
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, x: Tensor) -> Tensor:
        """
        Args:
            x: [bsz, seqlen, d_model]

        Returns:
            path_probs [bsz, n_paths] — probability distribution over paths
        """
        pooled = x.mean(dim=1)  # mean across sequence tokens
        logits = self.mlp(pooled)
        return self.softmax(logits)

    def select_path(self, probs: Tensor, deterministic: bool = True) -> int:
        """Return chosen path index deterministically (argmax) or sampled."""
        if deterministic:
            return probs.argmax(dim=-1).item()
        return torch.multinomial(probs, num_samples=1).item()


__all__ = ["RedSeaRouter"]
