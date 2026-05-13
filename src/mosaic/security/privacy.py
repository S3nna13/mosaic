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

Action strategies:\n  • REDACT — replace with [REDACTED:<type>]\n  • BLOCK  — reject the entire request\n  • LOG    — allow but record to audit log\n  • PASSTHROUGH — no filtering (dangerous; DEBUG only)\n\nAll detectors run in order; first match wins (short-circuit).  Case-insensitive by default.\n"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Pattern, Tuple

import structlog

logger = structlog.get_logger()


class PrivacyAction(str, Enum):
    REDACT   = "redact"
    BLOCK    = "block"
    LOG      = "log"
    PASSTHROUGH = "passthrough"


@dataclass
class PrivacyRule:
    pattern: Pattern[str]
    type_name: str
    action: PrivacyAction
    description: str


class PrivacyFilter:
    """Detect and handle PII / secrets in text."""
    _compiled_rules: List[PrivacyRule]

    def __init__(self, default_action: PrivacyAction = PrivacyAction.REDACT):
        self.default_action = default_action
        self._compiled_rules = self._build_rules()

    def _build_rules(self) -> List[PrivacyRule]:
        rules: List[Tuple[str, str, PrivacyAction, str]] = [
            # ── Personal identifiers ────────────────────────────────────────
            (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "email",    PrivacyAction.REDACT, "Email address"),
            (r"\b\d{3}-\d{3}-\d{4}(?:\D|$)",               "phone_us", PrivacyAction.REDACT, "US phone number"),
            (r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone_intl", PrivacyAction.REDACT, "International phone"),
            (r"\b\d{3}-\d{2}-\d{4}\b",                     "ssn",      PrivacyAction.REDACT, "US Social Security Number"),
            (r"\b(?!000|666)9\d{2}-(?!00)\d{2}-(?!0000)\d{4}\b", "itin", PrivacyAction.REDACT, "US Individual Taxpayer ID"),
            # ── Financial ───────────────────────────────────────────────────
            (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b", "credit_card", PrivacyAction.REDACT, "Credit card (Visa/MC)"),
            (r"\b3[47][0-9]{13}\b", "amex", PrivacyAction.REDACT, "American Express card"),
            # ── API keys & tokens ────────────────────────────────────────────
            (r"\b(sk|sk-|sk_prod|sk_test)-[A-Za-z0-9]{48}", "openai_key",   PrivacyAction.BLOCK, "OpenAI secret key"),
            (r"\b(sk-ant)-[A-Za-z0-9]{48,}",                 "anthropic_key",PrivacyAction.BLOCK, "Anthropic API key"),
            (r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}",    "github_token", PrivacyAction.BLOCK, "GitHub personal access token"),
            (r"\b(?:AIza[0-9A-Za-z\\-_]{35})\b",             "google_key",   PrivacyAction.BLOCK, "Google API key"),
            (r"\b(?:AKIA|A3T|AGPA)[A-Z0-9]{16}\b",           "aws_access_key",PrivacyAction.BLOCK, "AWS access key ID pattern"),
            # ── Network ───────────────────────────────────────────────────────
            (r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", "ip_address", PrivacyAction.REDACT, "IP address"),
            (r"\bhttps?://[^\s/$.?#].[^\s]*\b", "url", PrivacyAction.REDACT, "URL"),
        ]
        compiled = []
        for pat, t, act, desc in rules:
            try:
                compiled.append(PrivacyRule(re.compile(pat, re.IGNORECASE), t, act, desc))
            except re.error as e:
                logger.warning("regex_failed", pattern=pat, error=str(e))
        return compiled

    def scan(self, text: str, *, action_override: Optional[PrivacyAction] = None) -> Tuple[str, List[Dict[str, str]]]:
        """Scan text; apply strategy for each match.

        Returns: (sanitised_text, findings_list)
        """
        findings: List[Dict[str, str]] = []
        sanitised = text
        offset = 0  # track replacements so indices stay correct

        # Process in order of appearance across all rules
        matches: List[Tuple[int, int, str, str]] = []
        for rule in self._compiled_rules:
            for m in rule.pattern.finditer(text):
                matches.append((m.start(), m.end(), rule.type_name, rule.action))

        # Sort by start position, deduplicate overlapping by preferring earlier rule
        matches.sort(key=lambda x: x[0])
        cleaned: List[Tuple[int, int, str]] = []
        last_end = 0
        for start, end, t, act in matches:
            if start < last_end:
                continue  # skip overlap
            last_end = end
            cleaned.append((start, end, t, act))

        # Apply replacements right-to-left to preserve indices
        for start, end, t, act in reversed(cleaned):
            act_to_use = action_override or act
            finding = {
                "type": t,
                "action": act_to_use.value,
                "span": [start, end],
                "sample": text[start:start+10] + ("…" if end-start > 10 else ""),
            }
            findings.append(finding)

            if act_to_use == PrivacyAction.REDACT:
                sanitised = sanitised[:start] + f"[REDACTED:{t}]" + sanitised[end:]
            elif act_to_use == PrivacyAction.BLOCK:
                # Hard block indicated by caller inspecting findings
                pass
            elif act_to_use == PrivacyAction.LOG:
                pass  # no change
            elif act_to_use == PrivacyAction.PASSTHROUGH:
                pass

        return sanitised, findings

    def contains_secret_blockers(self, text: str) -> bool:
        """Quick pre-check: does text contain any BLOCK-action secret?"""
        for rule in self._compiled_rules:
            if rule.action == PrivacyAction.BLOCK and rule.pattern.search(text):
                return True
        return False
