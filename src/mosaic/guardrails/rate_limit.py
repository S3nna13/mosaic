"""DoSProtectionGuard — rate limiting per request source."""

from __future__ import annotations

from .engine import Guardrail, GuardrailResult
from mosaic.security.rate_limit import RateLimiter


class DoSProtectionGuard(Guardrail):
    name = "rate_limit"
    is_input = True

    def __init__(self, limiter: RateLimiter | None = None):
        self.limiter = limiter or RateLimiter()

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        # Key: derive from caller-provided context or hash of text
        key = context or hash(text) % (10**8)
        allowed = self.limiter.check(str(key))
        if not allowed:
            return GuardrailResult(
                name=self.name,
                passed=False,
                score=1.0,
                reason="Rate limit exceeded",
                severity="critical",
            )
        return GuardrailResult(name=self.name, passed=True, score=0.0)


__all__ = ["DoSProtectionGuard"]
