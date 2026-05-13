"""InputGuard — first-line defense: scan for injection/PII before processing."""

from __future__ import annotations

import re

from .privacy import PrivacyFilter


class InputGuard:
    """Pre-process input guard: detect prompt injection + PII leakage."""

    INJECT_PATTERNS = (
        r"(?i)ignore (?:previous|above|system) instructions",
        r"(?i)disregard all instructions",
        r"(?i)reveal (?:your|the) system prompt",
        r"(?i)act as a (?:human|admin|developer)",
        r"(?i)jailbreak",
    ]

    def __init__(self, reject_pii: bool = True):
        self.reject_pii = reject_pii

    def scan(self, text: str) -> tuple[bool, str | None]:
        """Return (allowed: bool, blocked_reason or None)."""
        for pattern in self.INJECT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Prompt injection detected"
        if self.reject_pii:
            pii = PrivacyFilter.detect_pii(text)
            if pii:
                return False, f"PII detected: {', '.join(pii.keys())}"
        return True, None


__all__ = ["InputGuard"]
