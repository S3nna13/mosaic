# Changelog

All notable changes to MOSAIC are documented here.

## [0.3.0] — 2026-05-13

### Added
- **Unified framework** combining Moses (memory-first transformer), Setus (hardened security), and Aigis (multi-provider orchestration, eval)
- **Exodus Memory** — 3-tier hierarchical store (scratch → episode → archive) with LRU eviction and optional SQLite persistence
- **Sinai Registers** — learnable, persistent tokens injected into transformer attention
- **RedSea Router** — fast/deliberate/search/agent/memory mode classifier via MLP
- **StaffDecoder** — orchestrates routing, memory, generation, guardrails, verification; auto-escalates on low stability
- **14 OWASP guardrails** — jailbreak, injection, toxicity, PII, secrets, context window, RAG poisoning, output validation, constitutional, factual, hallucination, rate limit
- **ArkLedger** — Merkle-chained audit log (append-only, hash-verified, SIEM-exportable)
- **GuardrailTuner** — adaptive threshold auto-tuning based on live false-positive rate
- **Multi-provider adapters** — OpenAI, Anthropic, Ollama (local server), Local (HuggingFace) with circuit breaker + exponential backoff
- **SafeToolRunner** — async subprocess executor with safe_mode IP validation, environment filtering, timeouts, output parsing
- **Tool Registry + 50+ built-in tools** — recon (nmap, dns), vuln (nuclei, nikto), scan (sqlmap, metasploit), monitor (zeek, suricata), defense (iptables, ufw), utility
- **MITRE ATT&CK Mapper** — automatic technique classification for security findings
- **Synthetic Data Generator** — infinite instruction-response pairs via teacher models (OpenAI/Anthropic)
- **Trainer + Checkpointing** — SFT with gradient accumulation, epoch/step tracking, checkpoint save/load
- **RLHF Scaffold** — GRPO/PPO placeholders for alignment
- **Benchmark Harness (HELM-style)** — runs TruthfulQA, GSM8K, HumanEval, ToxicityPrompts, MMLU with metrics
- **VectorStore Memory Backend** — optional semantic search over Archive via Chroma/NumPy
- **Multi-modal vision support** — ImageInput, MultiModalMessage; GPT-4o and Claude 3.5 Sonnet vision-ready

### Changed
- Unified configuration model in `src/mosaic/core/schema.py` using Pydantic v2
- FastAPI application with 10+ endpoints under `src/mosaic/api.py`
- Click CLI with commands: chat, serve, eval, guard, config, tools, train
- Dashboard — reactive single-page HTML (Chart.js) at `/dashboard`
- Project layout: `src/mosaic/` — modular 14 subpackages, comprehensive documentation in `docs/`

### Security
- **Defense-in-depth:** 14 OWASP rails + PrivacyFilter + RateLimit + SafeToolRunner
- **Safe-mode IP whitelist** blocks external network calls by default
- **Audit trail:** every decode/tool/guardrail outcome recorded in ArkLedger with hash chain
- **MITRE enrichment:** guardrail failures tagged with ATT&CAP technique IDs for SOC correlation

## [Planned] — v1.1.0

### To be implemented
- Full GRPO/PPO loop with reward model
- Real vision encoder integration (CLIP, SigLIP)
- Qdrant/pgvector persistence for VectorStore
- Audio I/O (Whisper, SpeechT5)
- Docker image scanning + SBOM generation
- Kubernetes rollout strategies + canary deployments

---

**MOSAIC** is a synthesis project. See README.md for architecture and usage.
