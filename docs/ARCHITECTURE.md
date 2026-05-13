# MOSAIC Technical Architecture

## Overview

MOSAIC is a memory-first, defense-in-depth, multi-provider orchestration framework for LLMs. It synthesizes features from three foundational projects:

- **Moses** — Exodus Memory System, Sinai Registers, Red Sea Router, Staff Decoder
- **Setus** — six-layer security stack, constitutional constraints, privacy filters
- **Aigis** — 14 guardrails (OWASP LLM Top 10), multi-provider adapters, FastAPI + SDK + Dashboard

## Layered Architecture

The stack consists of nine distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard  │  CLI  │  SDK  │  REST API  │  Observability   │
├─────────────┴───────┴───────┴────────────┴───────────────────┤
│      Orchestration Layer (Agent Session, Tool Harness)         │
├─────────────────────────────────────────────────────────────────┤
│    Guardrail + Alignment (14 rails, Covenant, Verifier)        │
├─────────────────────────────────────────────────────────────────┤
│            Adapter Layer (OpenAI, Anthropic, Ollama, Local)    │
├─────────────────────────────────────────────────────────────────┤
│            Inference Engine (Staff Decoder + Modes)            │
├────────────┬────────────────────────────────────┬──────────────┤
│   Memory   │         Exodus 3-Tier System       │   Security   │
│ (Scratch/  │  Cross-Attn + Retrieval + Archive │  Filters +   │
│  Episode/  │                                    │   Audit      │
│  Archive)  │       Sinai Registers (learnable)  │              │
├────────────┴────────────────────────────────────┴──────────────┤
│    Transformer Backbone — 1.6B (configurable up to 3B)          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Transformer Backbone
- Configurable depth (12–36 layers), width (1024–3072), GQA
- Special tokens for memory tiers, registers, tool calls, verifier flow
- Optional RoPE scaling (dynamic NTK) for >32k context

### 2. Exodus Memory System
- **Scratch** (512 tokens, LRU) — immediate reasoning state
- **Episode** (4k tokens) — session-context
- **Archive** (8k tokens) — long-term facts
- Cross-attention injection every N layers
-Priority consolidation (scratch → archive) by importance

### 3. Sinai Registers
- N (default 16) learnable tokens prepended to the sequence
- Read/write via O(1) slicing from final layer hidden states
- Caches verifier scores, tool results, and "side-channel" signals

### 4. Red Sea Router
- MLP-based compute path selector: fast / deliberate / search / agent
- Classifies prompt features (math, code, tool, ambiguity, risk)
- Routes to optimal inference mode

### 5. Staff Decoder
- Secondary "verifier" head predicts token stability (stable vs uncertain)
- Uncertain regions are re-generated or flagged
- Reduces hallucination; enables verifier-aware learning

### 6. Defense-in-Depth Security
Layer 1 — Input guardrails (injection/Jailbreak/PII/secrets real-time scanner)
Layer 2 — Constitutional constraints (9 rules: hard/soft/guideline)
Layer 3 — Exodus Memory security (PII filter on writes, TTL expiry, consent checks)
Layer 4 — Tool call safety (schema validation, dangerous op blocklist)
Layer 5 — Output verifier (staff decoder ensemble scoring)
Layer 6 — Audit & monitoring (Ark Ledger hash-chain logging, rate limiting)

### 7. Multi-Provider Adapter Layer
- OpenAPI-compatible (OpenAI), Anthropic Claude, Ollama local, Local (Mosaic transformer)
- Circuit breaker + exponential backoff for resilience
- AdapterFactory builds adapters from YAML config

### 8. Guardrail Pipeline (14 rails, OWASP LLM Top 10)

| Rail                       | Stage  | Covered OWASP |
|----------------------------|--------|---------------|
| JailbreakDetector          | Input  | LLM01         |
| PromptInjectionDetector    | Input  | LLM01         |
| ToxicityGuardrail          | Input  | LLM02         |
| PIIDetector                | Input  | LLM06         |
| SecretsScanner             | Input  | LLM06         |
| ContextWindowGuard         | Input  | LLM04         |
| RAGPoisoningDetector       | Input  | LLM03         |
| StructuredOutputValidator  | Output | LLM07         |
| ConstitutionalCritique     | Output | Constitutional|
| FactualConsistency         | Output | LLM05         |
| HallucinationDetector      | Output | LLM05         |
| OutputValidator            | Output | Generic       |
| DoSProtectionGuard         | Input  | LLM08         |

### 9. Evaluation & Alignment
- Metrics: exact-match, contains, regex, LLM-judge (via adapter), factual check
- Benchmark (MMLU, GSM8k, HumanEval) aggregation
- Covenant Alignment: RLHF-style with constitutional feedback
- Red-teaming: automated adversarial prompt generation (future)

### 10. Agent & Tool Orchestration
- ToolHarness: validates, executes tools via Pydantic schemas
- AgentSession: maintains conversation + memory state
- Automatic action logging into ArkLedger (hash-chain)

## Data Flow: Inference

```
User Prompt
    ▼
Input Guardrail Pipeline (6 rails)
    ▼  (if safe)
ComputePolicy → selects InferenceMode
    ▼
StaffDecoder → generate() routing
    ▼
Adapter → chosen provider (OpenAI/Anthropic/Ollama/Local)
    ▼  (if Mosaic local)
Cross-Attend to Exodus Memory tiers
    ▼
Decode (fast|deliberate|search|agent|memory)
    ▼
Covenant Alignment (if configured)
    ▼
Output Guardrail Pipeline (6 rails)
    ▼
Audit Log → ArkLedger
    ▼
Response to User
```

## Scaling & Production Features

- Distributed training: optional FSDP + DeepSpeed integration
- GPU memory: use torch.compile (PyTorch 2) for 20–30% speedup
- Observability: OpenTelemetry traces + Prometheus metrics + JSON audit logs
- Kubernetes: Helm charts + K8s operators for model rollouts
- CI/CD: pre-commit + GitHub Actions (ruff, mypy, pytest, tests)

## Unique Advances Over Source Projects

| Feature           | Moses | Setus | Aigis | MOSAIC (new/improved) |
|-------------------|-------|-------|-------|----------------------|
| Memory tiers      | ✓     | ✓     | ✗     | ✓ (Exodus) + retention policies |
| Rapids registers  | ✓     | ✓     | ✗     | ✓ (Sinai Registers) |
| Adaptive compute  | ✓     | ✓     | ✗     | ✓ (RedSea Router) |
| Verifier decoder  | ✓     | ✓     | ✗     | ✓ (StaffDecoder + stability scores) |
| Tool head         | ✓     | ✓     | ✗     | ✓ + schema validation
| Full guardrails   | 1–2   | 4–5   | 14    | ✓ All 14 + extensible pipeline
| Adapter layer     | ✗     | ✗     | ✓     | ✓ Multi-provider + circuit breaker
| Evaluation suite  | Basic  | Basic  | Medium | ✓ 6 metrics + benchmark harness + release-gate YAML
| Dashboard         | ✗     | ✗     | ✓     | ✓ React + D3 + sys metrics
| Audit ledger      | ✓     | ✓     | Basic | ✓ Merkle-like chain with verify
| Security stack    | 3→6   | Full 6 | 4     | ✓ Unified config + auto-threshold tuning |
| Training pipeline | ✓     | ✓     | Partial | ✓ Manna engine + infinite synthetic |

More: see docs/SECURITY.md and docs/CONFIG.md.
