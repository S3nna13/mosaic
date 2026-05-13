"""MultiModalAdapter mixin — adds vision capability to any BaseAdapter.

Usage:
  class OpenAIVisionAdapter(MultiModalAdapter, OpenAIAdapter):
      pass
"""
from __future__ import annotations

from mosaic.adapters.base import BaseAdapter
from mosaic.multimodal.vision import MultiModalMessage


class MultiModalAdapter(BaseAdapter):
    """Mixin that overrides chat() to accept MultiModalMessage objects with images."""

    def _messages_to_chat(self, messages: list):
        """Convert MultiModalMessage list to provider-native format."""
        # This mirrors the per-adapter logic but centralizes it
        result = []
        for m in messages:
            if isinstance(m, MultiModalMessage):
                parts = [{"type": "text", "text": m.content}]
                for img in m.images or []:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": img.source}
                    })
                result.append({"role": m.role, "content": parts})
            elif hasattr(m, 'images') and m.images:
                # Handle base Message with images field
                parts = [{"type": "text", "text": m.content}]
                for img in m.images or []:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": img.source}
                    })
                result.append({"role": m.role, "content": parts})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

__all__ = ["MultiModalAdapter"]
