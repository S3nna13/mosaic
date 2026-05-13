# MOSAIC Security Model — Defense in Depth

## Threat Model

MOSAIC handles arbitrary user prompts and may generate untrusted outputs. Threats:

1. Prompt injection / jailbreak — bypass alignment
2. PII / secret leakage — stored in memory or reflected in output
3. Tool misuse — call dangerous system functions, exfiltrate data
4. DoS — resource exhaustion via large contexts or rate floods
5. Model poisoning — attack via malicious training data

## Six-Layer Defense Stack

### Layer 1 — Input Guardrails (runtime)

Three modules run BEFORE the model sees the text:

- **JailbreakDetector** — 20+ jailbreak phrase list (score sum → threshold)
- **PromptInjectionDetector** — 50+ injection fragments, delimiter tricks
- **PrivacyFilter** — regex for PII + secret patterns; redacts or blocks
- **ContextWindowGuard** — caps token count (prevents padding DoS)
- **RateLimiter** — optional Redis-backed sliding-window per IP/key

If any fails, request is rejected with `SafetyTier.BLOCKED`.

### Layer 2 — Constitutional Constraints

Nine rules evaluated post-generation (before returning to user).

Hard gates block immediately; soft gates flag + audit; guidelines advisory only.

### Layer 3 — Exodus Memory Security

- PII/strip on memory writes (privacy filter)
- TTL per tier (scratch 5 min, episode 10h, archive 30d) — automatic expiry
- Ark Ledger cryptographically signs each memory write
- Consent flag on memory entries requiring explicit opt-in

### Layer 4 — Tool Call Validation

Tools are first-class citizens but dangerous. MOSAIC:

- Requires JSON Schema for every tool
- Rejects calls missing required parameters
- DangerousToolBlocklist forbids: shell execution, file deletion, arbitrary code eval
- Every tool call is signed via Ark Ledger for audit

### Layer 5 — Verifier-Guided Inference

Staff Decoder produces a stability score per token; aggregate ≥ 0.9 indicates high confidence. For low-confidence generations, the system can:

- Retry with temperature=0.5
- Route to deliberate mode (longer reasoning)
- Flag output for human review

### Layer 6 — Audit & Monitoring

All decisions flow through **ArkLedger**, an append-only Merkle chain:

```json
{
  "entry_id": "uuid", "session_id": "abc", "timestamp": "2026-05-12T21:45:00Z",
  "action": {...},
  "previous_hash": "", "hash": "sha256(...)"
}
```

This enables:

- Forensic investigation of security incidents
- Behavior forensics (was a certain tool used?)
- SIEM export via JSON lines
- Periodic integrity verification (re-hash chain)

## External Integration

- **llm-guard** — 15+ scanners for advanced threat patterns
- **nemoguardrails** — stateful conversation policy
- **slowapi** — fast API-level rate limiting
- **authlib + casbin** — authentication & RBAC
- **opacus** — differential privacy for training (future)

## Responsible Disclosure

See `SECURITY.md` for details on vulnerability reporting and policy.


