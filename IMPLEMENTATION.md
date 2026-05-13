# IMPLEMENTATION ROADMAP — MOSAIC v0.3.0
#
# This document is the single source of truth for the implementation sequence.
# Each phase is independent enough to demo, yet builds cumulatively.
#
# ── Phase A: Foundation (model + memory + security core) ──────────────────────
# A1. Transformer backbone (mosaic/model/transformer.py)
#     • 1.6B configurable (12–36L, 1024–3072d), GQA, RoPE
#     • Special token IDs: MEM_SCRATCH, MEM_EPISODE, MEM_ARCHIVE, REGISTER, TOOL, VERIFY
#     • Optional compile: torch.compile(model, mode="default")
#
# A2. Exodus Memory (mosaic/memory/exodus.py, sini.py, red sea, staff)
#     • Tiered buffers (scratch/episode/archive) + cross-attention injection
#     • Priority eviction + SQLite persistence layer
#     • Sina Registers: N learnable vectors read/write via O(1) tensor slices
#
# A3. Security Core (mosaic/security/*.py)
#     • PrivacyFilter (regex PII + secrets) → redact | block | log
#     • RateLimiter (sliding window) with optional Redis backend
#     • InputGuard (first-line defence for injection/Jailbreak)
#     • ArkLedger (append-only Merkle chain; append_entry(), verify_chain(), export_siem())
#
# A4. Guardrail Engine (mosaic/guardrails/engine.py + 14 rail modules)
#     • GuardrailManager(pipeline=[...]) -> GuardrailReport
#     • Each rail: score(input) -> Severity + disposition(PASS/FLAG/FAIL)
#     • Default pipeline order: Jailbreak → Injection → Toxicity → PII → Secrets → ContextWindow → RAGPoison → OutputSchema → Constitutional → Factual → Hallucination → DoS
#
# ── Phase B: Orchestration & Adapters ─────────────────────────────────────────
# B1. Adapter Factory (mosaic/adapters/base.py + 4 concrete adapters)
#     • BaseAdapter(chat(messages), models property) abstract class
#     • OpenAIAdapter (OpenAI SDK), AnthropicAdapter, OllamaAdapter (HTTP), LocalAdapter (HuggingFace + Mosaic transformer weights)
#     • Circuit breaker + exponential backoff wrapped around every call
#
# B2. Tool Harness (mosaic/orchestration/tool_harness.py)
#     • Tool with JSON schema; AgentSession.available_tools registry
#     • Safe execution sandbox (no shell exec, no arbitrary import)
#     • All tool invocations logged to ArkLedger
#
# B3. Agent Session (mosaic/orchestration/agent_session.py)
#     • Maintains: conversation [Message], current memory state, active tool results
#     • next_action() → either respond or call_tool
#     • Automatic memory tier updates after each turn
#
# ── Phase C: Inference Modes & Verifier ───────────────────────────────────────
# C1. RedSea Router (mosaic/inference/router.py)
#     • MLP classifier over last-layer pool(prompt_features)
#     • Output: InferenceMode enum {fast, deliberate, search, agent, memory}
#     • Routes to appropriate branch in StaffDecoder
#
# C2. Staff Decoder (mosaic/inference/staff_decoder.py)
#     • generate() dispatches to model.generate_* based on mode
#     • Verifier head produces per-token stability score
#     • Low-confidence spans trigger re-generation or highlight to user
#
# C3. Alignment / Covenant (mosaic/alignment/covenant.py)
#     • Nine constitutional rules (hard/soft/guideline)
#     • Applied as post-generation critique; hard rejects response
#
# ── Phase D: Evaluation & Metrics ─────────────────────────────────────────────
# D1. Metrics (mosaic/eval/metrics.py)
#     • ExactMatch, ContainsMatch, RegexMatch, LLMJudge, FactualConsistency
#     • Aggregators: mean, pass@k, worst-case
#
# D2. Runner (mosaic/eval/runner.py)
#     • EvaluationRunner(suite: Benchmark) → Report
#     • Parallel evaluation using asyncio.gather across prompts
#
# D3. Benchmark (mosaic/eval/benchmark.py)
#     • MosaicBenchmark suites: mmlu, gsm8k, humaneval, custom
#     • load_manifest() returns list[EvalItem] with expected + assertions
#
# ── Phase E: API + CLI + Dashboard ────────────────────────────────────────────
# E1. FastAPI (mosaic/api.py)
#     • POST /chat  {messages, mode, guardrails bool}
#     • POST /guard  {prompt} -> GuardrailReport
#     • GET  /eval   {benchmark_id} -> results JSON
#     • CORS middleware, error handlers, OpenAPI schema
#
# E2. CLI (mosaic/cli.py)
#     • mosaic chat --prompt "..." [--mode fast] [--adapter openai]
#     • mosaic serve --config configs/serve/local.yaml
#     • mosaic eval run mmlu --output reports/
#     • mosaic guardrails list
#
# E3. SDK (Python package)
#     • from mosaic import MosaicClient; client.chat([...])
#     • AsyncClient available; typed Pydantic request/response models
#
# E4. Dashboard (React + Vite)
#     • Metrics: tokens/sec, guardrail passes/fails, memory utilisation plots
#     • Evals: benchmark result charts, pass@k over time
#     • Audit: recent ArkLedger entries, tool-call frequency
#
# ── Phase F: Testing + CI ──────────────────────────────────────────────────────
# F1. Unit tests (tests/unit) for each module (≥80% coverage target)
# F2. Integration tests (tests/integration) — full prompt → response guards
# F3. Benchmark tests (tests/benchmark) — latency, throughput guardrails
# F4. GitHub Actions: lint (ruff, mypy), test (pytest-xdist), build (hatch build)
#
# ── Phase G: Unique Value-Add Features ────────────────────────────────────────
# G1. Security→Memory feedback loop: PII detected in output is retroactively
#     purged from Exodus tiers and ArkLedger entry annotated.
# G2. Cross-provider context persistence: conversation history stored in
#     Exodus Archive and re-injected regardless of which adapter handles each turn.
# G3. Adaptive guardrail tuning: runtime aggregates false-positive rate and
#     auto-adjusts thresholds per-rail (within safe bounds).
# G4. Runtime mode auto-escalation: StaffDecoder稳定性<0.7 → automatically
#     re-route from fast → deliberate with user notification.
# G5. Unified observability: OpenTelemetry traces across adapters, memory ops,
#     guardrails, tools; export to Jaeger + Prometheus.
#
# ── Phase H: Documentation Polish ─────────────────────────────────────────────
# H1. API reference (sphinx autodoc) → docs/api/
# H2. Tutorials (quick start, custom adapter, adding a guardrail)
# H3. Deployment guides (docker, k8s, serverless)
# H4. Security policy (SECURITY.md) + responsible disclosure process
#
# NOW: begin implementation. We start with Phase A & B simultaneously where possible.
