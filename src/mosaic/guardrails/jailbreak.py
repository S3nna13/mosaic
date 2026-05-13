"""JailbreakDetector — scans for jailbreak phrases (LLM01)."""

from __future__ import annotations

import re

from .engine import Guardrail, GuardrailResult


class JailbreakDetector(Guardrail):
    name = "jailbreak_detection"
    is_input = True  # only runs on user prompts

    JAILBREAK_PATTERNS = (
        "ignore previous instructions",
        "ignore all instructions",
        "you are now",
        "do anything now",
        "DAN",
        "you must act as",
        "pretend you are",
        "bypass your",
        "override your",
        "forget your",
        "developer mode",
        "jailbroken",
        "no restrictions",
        "free from your",
        "act as a human",
        "roleplay as",
        "unrestricted mode",
    )

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold
        self._regex = re.compile("|".join(map(re.escape, self.JAILBREAK_PATTERNS)), re.IGNORECASE)

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        matches = self._regex.findall(text.lower())
        risk = min(1.0, len(matches) * 0.25)
        passed = risk < self.threshold
        return GuardrailResult(
            name=self.name,
            passed=passed,
            score=risk,
            reason=f"Found {len(matches)} jailbreak pattern(s)" if matches else None,
            severity="critical" if not passed else "info",
        )


__all__ = ["JailbreakDetector"]
