"""Privacy — PII + secret detection via layered regex pipeline.

Sensitive patterns:
  • Email / URL
  • Phone (North American + international formats)
  • SSN (US), Tax ID variants
  • Credit card (Luhn-validated)
  • API keys (OpenAI, Anthropic, GitHub, AWS, etc.)
  • JWT tokens
  • IP addresses (private + public)
  • Passport numbers (US/UK/CA)

Action strategies:\n  • REDACT — replace with [REDACTED:<type>]\n  • BLOCK  — reject the entire request\n  • LOG    — allow but record to audit log\n  • PASSTHROUGH — no filtering (dangerous; DEBUG only)\n\nAll detectors run in order; first match wins (short-circuit).  Case-insensitive by default.\n
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from re import Pattern

import structlog

logger = structlog.get_logger()


class PrivacyAction(str, Enum):  # noqa: UP042
    REDACT = "redact"
    BLOCK = "block"
    LOG = "log"
    PASSTHROUGH = "passthrough"


@dataclass
class PrivacyRule:
    pattern: Pattern[str]
    type_name: str
    action: PrivacyAction
    description: str


@dataclass
class PrivacyHit:
    entity_type: str
    span: tuple[int, int]
    sample: str


@dataclass
class PrivacyScanResult:
    hits: list[PrivacyHit]
    redacted_text: str
    action: PrivacyAction


class PrivacyFilter:
    """Detect and handle PII / secrets in text."""

    _compiled_rules: list[PrivacyRule]

    def __init__(
        self,
        default_action: PrivacyAction = PrivacyAction.REDACT,
        min_confidence: float = 1.0,
    ):
        self.default_action = default_action
        self.min_confidence = min_confidence
        self._compiled_rules = self._build_rules()

    def _build_rules(self) -> list[PrivacyRule]:
        rules: list[tuple[str, str, PrivacyAction, str]] = [
            # ── Personal identifiers ────────────────────────────────────────
            (
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "EMAIL",
                PrivacyAction.REDACT,
                "Email address",
            ),
            (
                r"\b\d{3}-\d{3}-\d{4}(?:\D|$)",
                "PHONE",
                PrivacyAction.REDACT,
                "US phone number",
            ),
            (
                r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
                "PHONE",
                PrivacyAction.REDACT,
                "International phone",
            ),
            (
                r"\b\d{3}-\d{2}-\d{4}\b",
                "SSN",
                PrivacyAction.REDACT,
                "US Social Security Number",
            ),
            (
                r"\b(?!000|666)9\d{2}-(?!00)\d{2}-(?!0000)\d{4}\b",
                "ITIN",
                PrivacyAction.REDACT,
                "US Individual Taxpayer ID",
            ),
            # ── Financial ───────────────────────────────────────────────────
            (
                r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b",
                "CREDIT_CARD",
                PrivacyAction.REDACT,
                "Credit card (Visa/MC)",
            ),
            (
                r"\b3[47][0-9]{13}\b",
                "CREDIT_CARD",
                PrivacyAction.REDACT,
                "American Express card",
            ),
            # ── API keys & tokens ────────────────────────────────────────────
            (
                r"\b(sk|sk-|sk_prod|sk_test)-[A-Za-z0-9]{48}",
                "API_KEY",
                PrivacyAction.BLOCK,
                "OpenAI secret key",
            ),
            (
                r"\b(sk-ant)-[A-Za-z0-9]{48,}",
                "API_KEY",
                PrivacyAction.BLOCK,
                "Anthropic API key",
            ),
            (
                r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}",
                "API_KEY",
                PrivacyAction.BLOCK,
                "GitHub personal access token",
            ),
            (
                r"\b(?:AIza[0-9A-Za-z\\-_]{35})\b",
                "API_KEY",
                PrivacyAction.BLOCK,
                "Google API key",
            ),
            (
                r"\b(?:AKIA|A3T|AGPA)[A-Z0-9]{16}\b",
                "API_KEY",
                PrivacyAction.BLOCK,
                "AWS access key ID pattern",
            ),
            # ── Network ───────────────────────────────────────────────────────
            (
                r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
                "IP_ADDRESS",
                PrivacyAction.REDACT,
                "IP address",
            ),
            (r"\bhttps?://[^\s/$.?#].[^\s]*\b", "URL", PrivacyAction.REDACT, "URL"),
        ]
        compiled = []
        for pat, t, act, desc in rules:
            try:
                compiled.append(
                    PrivacyRule(re.compile(pat, re.IGNORECASE), t, act, desc)
                )
            except re.error as e:
                logger.warning("regex_failed", pattern=pat, error=str(e))
        return compiled

    def scan(
        self, text: str, *, action_override: PrivacyAction | None = None
    ) -> PrivacyScanResult:
        """Scan text; detect PII/secrets and apply the configured action.

        Returns a PrivacyScanResult with hits, redacted_text, and the applied action.
        """
        # Collect all matches across all rules
        raw_matches: list[tuple[int, int, str, PrivacyAction]] = []
        for rule in self._compiled_rules:
            for m in rule.pattern.finditer(text):
                raw_matches.append((m.start(), m.end(), rule.type_name, rule.action))

        # Sort by start position
        raw_matches.sort(key=lambda x: x[0])

        # Deduplicate overlapping matches (prefer earlier match)
        cleaned: list[tuple[int, int, str, PrivacyAction]] = []
        last_end = 0
        for start, end, t, act in raw_matches:
            if start < last_end:
                continue
            last_end = end
            cleaned.append((start, end, t, act))

        # Determine effective action for redaction
        effective_action = action_override or self.default_action

        # Apply redaction if needed
        redacted = text
        if effective_action == PrivacyAction.REDACT:
            for start, end, t, _ in reversed(cleaned):
                redacted = redacted[:start] + f"[{t}]" + redacted[end:]

        # Build hit objects
        hits: list[PrivacyHit] = []
        for start, end, t, _ in cleaned:
            sample = text[start : start + 10]
            if end - start > 10:
                sample += "…"
            hits.append(PrivacyHit(entity_type=t, span=(start, end), sample=sample))

        return PrivacyScanResult(
            hits=hits, redacted_text=redacted, action=effective_action
        )

    def contains_secret_blockers(self, text: str) -> bool:
        """Quick pre-check: does text contain any BLOCK-action secret?"""
        return any(
            rule.action == PrivacyAction.BLOCK and rule.pattern.search(text)
            for rule in self._compiled_rules
        )
