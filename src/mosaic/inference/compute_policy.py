"""ComputePolicy — router that selects inference mode from prompt characteristics."""

from __future__ import annotations

from typing import Any

from .modes import InferenceMode


class ComputePolicy:
    """Analyses prompt and selects optimal inference mode + compute path."""

    MATH_KEYWORDS = (
        "equation", "calculate", "integral", "derivative", "solve", "math",
        "algebra", "geometry", "calculus", "probability", "theorem", "proof",
    )
    CODE_KEYWORDS = (
        "code", "function", "implement", "algorithm", "programming", "class",
        "def ", "import ", "script", "debug", "fix", "refactor", "api",
    )
    TOOL_KEYWORDS = (
        "search", "browse", "fetch", "get", "retrieve", "query", "api",
        "http", "send", "tool", "call", "execute", "run", "list",
    )
    AMBIGUOUS_KEYWORDS = (
        "maybe", "uncertain", "unclear", "depends", "ambiguous",
        "could be", "might be", "either", "probably", "possibly",
    )
    HIGH_RISK_KEYWORDS = (
        "critical", "important", "urgent", "must", "should",
        "careful", "dangerous", "risk", "harm", "security", "admin",
    )

    def classify(self, text: str) -> dict[str, Any]:
        """Return feature dict for the given prompt."""
        lower = text.lower()
        is_math = any(kw in lower for kw in self.MATH_KEYWORDS)
        is_code = any(kw in lower for kw in self.CODE_KEYWORDS)
        is_tool_task = any(kw in lower for kw in self.TOOL_KEYWORDS)
        is_ambiguous = any(kw in lower for kw in self.AMBIGUOUS_KEYWORDS)
        is_long_context = len(text.split()) > 500
        risk_level = 0
        if is_ambiguous:
            risk_level += 1
        if is_math:
            risk_level += 1
        if is_tool_task:
            risk_level += 1
        if any(kw in lower for kw in self.HIGH_RISK_KEYWORDS):
            risk_level += 2
        return {
            "is_math": is_math,
            "is_code": is_code,
            "is_tool_task": is_tool_task,
            "is_ambiguous": is_ambiguous,
            "is_long_context": is_long_context,
            "risk_level": risk_level,
        }

    def select_mode(self, classification: dict[str, Any]) -> InferenceMode:
        """Choose inference mode based on classification."""
        if classification["is_tool_task"]:
            return InferenceMode.AGENT
        if classification["is_code"] and classification["risk_level"] >= 2:
            return InferenceMode.SEARCH
        if classification["is_math"]:
            return InferenceMode.SEARCH
        if classification["is_ambiguous"]:
            return InferenceMode.DELIBERATE
        return InferenceMode.FAST


__all__ = ("ComputePolicy"]
