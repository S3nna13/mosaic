"""Multi-modal vision + text capabilities.

Exposes:
  - VisionEncoder abstraction + CLIPVisionEncoder implementation
  - ImageInput dataclass for local/remote/image data
  - MultiModalMessage for text+image prompts
  - MultiModalAdapter Mixin to extend any BaseAdapter with vision support
"""

from __future__ import annotations

from .vision import CLIPVisionEncoder, ImageInput, MultiModalMessage, VisionEncoder

__all__ = [
    "CLIPVisionEncoder",
    "ImageInput",
    "MultiModalMessage",
    "VisionEncoder",
]
