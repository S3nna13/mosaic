"""Multi-modal vision encoder base + CLIP-style image projector.

Future: integrate with OpenAI GPT-4o, Claude 3.5 Sonnet vision, or local SigLIP.
This module provides the contract for image→embedding and image+text→response.
"""
from __future__ import annotations
import io

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from PIL import Image

try:
    import torch  # noqa: F401
    import torchvision.transforms as t  # noqa: F401
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False


@dataclass
class ImageInput:
    """Encapsulates an image reference (URL, file path, or base64 data)."""
    source: str  # url or filesystem path
    mime_type: str = "image/jpeg"
    data: bytes | None = None  # raw bytes if already loaded

    def load(self) -> Image.Image:
        if self.data:
            return Image.open(io.BytesIO(self.data))
        return Image.open(self.source)


class VisionEncoder(ABC):
    """Abstract encoder — maps image → embedding vector."""
    @abstractmethod
    def encode(self, image: Image.Image) -> np.ndarray:
        pass


class CLIPVisionEncoder(VisionEncoder):
    """CLIP ViT-B/16 visual encoder (uses open_clip if available)."""
    def __init__(self, model_name: str = "ViT-B-16"):
        try:
            import open_clip
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name, pretrained="openai")
            self.model.eval()
        except ImportError:
            # Fallback: random projection (for testing)
            self.model = None
            self.preprocess = None

    def encode(self, image: Image.Image) -> np.ndarray:
        if self.model is None:
            # Dummy 512-d vector
            return np.random.randn(512).astype(np.float32)
        # Real implementation would preprocess + forward through vit
        raise NotImplementedError("Connect open_clip for real encoding")


class MultiModalMessage:
    """Message that can carry both text and images."""
    def __init__(self, role: str, content: str, images: list[ImageInput] | None = None):
        self.role = role
        self.content = content
        self.images = images or []

    def as_openai_payload(self) -> dict:
        """Convert to OpenAI vision message format."""
        parts = [{"type": "text", "text": self.content}]
        for img in self.images:
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"file://{img.source}" if img.data is None else "data:image/jpeg;base64,..."}
            })
        return {"role": self.role, "content": parts}


__all__ = ["CLIPVisionEncoder", "ImageInput", "MultiModalMessage", "VisionEncoder"]
