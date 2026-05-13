"""MOSAIC core model — transformer + memory-native architecture."""

from __future__ import annotations

# Import errors are helpful: they guide dependency installation

try:
    from .config import MosaicConfig
except ImportError as e:
    raise ImportError(f"MosaicConfig unavailable: {e}") from e


# Optional heavy imports (torch)
try:
    from .model import MosaicForCausalLM  # type: ignore
    from .transformer import MosaicTransformer  # type: ignore
    from .verifier import VerifierHead  # type: ignore
except ImportError:
    MosaicTransformer = None  # type: ignore
    MosaicForCausalLM = None  # type: ignore
    VerifierHead = None  # type: ignore


__all__ = [
    "MosaicConfig",
    "MosaicForCausalLM",
    "MosaicTransformer",
    "VerifierHead",
]
