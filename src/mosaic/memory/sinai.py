"""Sinai Registers — rapid-access learnable tokens for O(1) state."""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Optional


class SinaiRegisters(nn.Module):
    """Learnable register tokens injected into the sequence.

    Registers are learnable position embeddings that are prepended to every
    sequence. They are updated each forward pass by the transformer and can
    be read in O(1) time from the last layer's register slice — no retrieval.

    Used for: quick-access facts, intermediate reasoning cache, tool outputs,
    verifier scores, or any state that needs instant access without memory lookup.
    """

    def __init__(self, config):
        super().__init__()
        self.n_registers = config.n_registers
        self.d_model = config.d_model
        # Learnable register embeddings tied to batch dimension
        self.register = nn.Parameter(torch.randn(1, config.n_registers, config.d_model) * 0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [bsz, seqlen, d_model]
        batch_size = x.shape[0]
        regs = self.register.expand(batch_size, -1, -1)  # [bsz, n_reg, d_model]
        return torch.cat([regs, x], dim=1)  # prepend registers

    def read(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """Extract register states from the final layer's hidden states.

        Args:
            hidden_states: [bsz, seqlen, d_model] final layer output

        Returns:
            register_states: [bsz, n_reg, d_model]
        """
        return hidden_states[:, : self.n_registers, :]

    def update(self, hidden_states: torch.Tensor, new_values: torch.Tensor) -> torch.Tensor:
        """Replace register embeddings in hidden states (in-place friendly copy)."""
        updated = hidden_states.clone()
        updated[:, : self.n_registers, :] = new_values
        return updated


__all__ = ["SinaiRegisters"]
