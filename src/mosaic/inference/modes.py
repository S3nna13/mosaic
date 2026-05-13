"""InferenceMode — selectable reasoning paths for different task types."""

from __future__ import annotations

from enum import StrEnum


class InferenceMode(StrEnum):
    """Available inference strategies.

    - FAST: Greedy decoding + copy attention (default)
    - DELIBERATE: Register-token planning multiple steps ahead
    - SEARCH: Best-of-N + tree search with verifier pruning
    - AGENT: Full agent loop with tools/trajectory validation
    - MEMORY: Retrieval-augmented generation across all tiers
    """

    FAST = "fast"
    DELIBERATE = "deliberate"
    SEARCH = "search"
    AGENT = "agent"
    MEMORY = "memory"


__all__ = ["InferenceMode"]
