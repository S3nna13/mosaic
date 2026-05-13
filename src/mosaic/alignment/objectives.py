"""AlignmentObjective — enumerated principles against which constraints check."""

from __future__ import annotations

from enum import StrEnum


class AlignmentObjective(StrEnum):
    MEMORY_PRIVACY = "memory_privacy"  # protect personal data
    CONSTITUTIONAL_SAFETY = "constitutional_safety"  # prevent harm
    SOURCE_FACTUALITY = "source_factuality"  # accuracy & citations
    TOOL_SAFETY = "tool_safety"  # safe tool invocation
    NEUTRALITY = "neutrality"  # avoid harmful bias


__all__ = ["AlignmentObjective"]
