# MOSAIC — Memory-First, Defense-in-Depth, Multi-Modal LLM Framework

**A unified synthesis of Moses (memory-first transformer), Setus (hardened security stack), and Aigis (multi-provider orchestration and evaluation) — plus Aurelius-inspired training, tool-use, and multi-modal capabilities.**

```
pip install -e '.[all]'   # install torch, transformers, openai, anthropic, fastapi, structlog, yaml, chromadb, etc.
mosaic serve --reload
open http://localhost:8000/dashboard
```

---

## Key Features

### 1. Hierarchical Three-Tier Memory (Exodus)
Scratch (512 tokens, short-term reasoning) → Episode (4k, conversational context) → Archive (persistent semantic store).  
Cross-attention injection keeps memory grounded in generation. Optional VectorStore (Chroma/NumPy) enables semantic similarity search across Archive.

### 2. Verifier-Aware Inference (StaffDecoder + RedSea Router)
Classifier routes prompts to `fast | deliberate | search | agent | memory` modes.  
Low stability scores (per-token confidence) automatically triggers re-generation in deliberate mode with memory hindsight.

### 3. Defense-in-Depth Security
14 OWASP LLM Top-10 guardrails running in an async pipeline:
`jailbreak · injection · toxicity · pii · secrets · context_window · rag_poisoning · structured_output · constitutional · factual · hallucination · rate_limit`

Integrated with **PrivacyFilter** (PII/secret redaction), **ArkLedger** (Merkle-chained audit log), and **SafeToolRunner** (subprocess sandboxing with safe-mode IP validation).

### 4. Multi-Provider Adapter Architecture
Plug-and-play backends: OpenAI, Anthropic, Ollama (local), Local (HuggingFace).  
Circuit breaker + exponential backoff. Same interface for all providers.

### 5. Tool Use & Safe Execution
~50 built-in security/utility tools (nmap, nuclei, sqlmap, zeek, ufw, etc.) across 6 layers.  
All executions are validated, env-filtered, timeout-protected, and audited to ArkLedger.

### 6. Training + Synthetic Data
Generate infinite instruction-response pairs via teacher models.  
SFT trainer with gradient accumulation + checkpointing. RLHF scaffold (GRPO/PPO).

### 7. Benchmark Harness (HELM-style)
Run scenarios: TruthfulQA, GSM8K, HumanEval, ToxicityPrompts, MMLU.  
Metrics: exact_match, contains, LLM-as-judge, code_exec pass@k.

### 8. Multi-Modal (Vision)
Built-in vision encoder stubs (CLIP) and image-capable adapters.  
Send `ImageInput` with messages; OpenAI GPT-4o and Claude 3.5 Sonnet vision supported.

---

## Project Layout

```
mosaic/
├── src/mosaic/
│   ├── model/           # GQA transformer, Sinai learnable registers
│   ├── memory/          # Exodus (3-tier) + VectorStore (semantic search)
│   ├── security/        # privacy, rate_limit, input_guard
│   ├── guardrails/      # 14 OWASP rails + engine + adaptive tuner
│   ├── adapters/        # openai, anthropic, ollama, local backends
│   ├── tools/           # SafeToolRunner, registry (+50 tools), MITRE mapper
│   ├── train/           # SyntheticGenerator, Trainer, RLTrainer
│   ├── eval/            # metrics, runner, benchmark
│   ├── inference/       # RedSea Router, StaffDecoder
│   ├── multimodal/      # vision encoders, image messages
│   ├── orchestration/   # ToolHarness, AgentSession
│   ├── audit/           # ArkLedger
│   ├── api.py           # FastAPI REST
│   ├── cli.py           # Click CLI
│   └── core/            # config + Pydantic schemas
├── configs/
│   ├── training/pretrain.yaml
│   ├── serve/local.yaml
│   ├── eval/release_gates.yaml
│   └── eval/scenarios/ (TruthfulQA, GSM8K, HumanEval, Toxicity)
├── tests/{unit,integration}
├── docs/{ARCHITECTURE,SECURITY,CONFIG,DEVELOP,API,DEPLOYMENT,TRAINING,TOOLS,MULTIMODAL}
├── dashboard/index.html  # reactive metrics dashboard
├── Makefile
├── pyproject.toml
└── README.md
```

---

## Quick Start

**1. Install**

```bash
git clone <your-mosaic-repo>
cd mosaic
python -m venv .venv && source .venv/bin/activate
pip install -e '.[all]'
pre-commit install   # optional: linting hooks
```

**2. Configure**

```bash
# Edit configs/serve/local.yaml — set your OpenAI/Anthropic API keys, choose adapter
mosaic config configs/serve/local.yaml
```

**3. Run**

```bash
# Start the API server
mosaic serve --reload

# In another terminal, chat
mosaic chat --prompt "Explain quantum entanglement" --adapter openai

# Run a benchmark
mosaic eval --benchmark --limit 10

# List security tools
mosaic tools list --layer recon

# Generate synthetic data
mosaic train synthetic --template code --n 20
```

**4. Dashboard**

Open http://localhost:8000/dashboard for live request-rate, guardrail hit-rate, latency, and stability score charts.

---

## API Reference

`POST /chat/completions` — Chat completion with full MOSAIC stack

```json
{
  "messages": [{"role": "user", "content": "Hello", "images": [{"source": "https://..."}]}],
  "adapter": "openai",
  "temperature": 0.7,
  "max_tokens": 1024,
  "guard": true,
  "audit": true
}
```

`POST /guard` — Run just the guardrail pipeline  
`GET /status` — System health + loaded adapters  
`GET /metrics` — Prometheus exposition format  
`POST /tools/{name}` — Execute a tool  
`POST /train/sft` — Start synthetic-data-driven SFT job  
`GET /dashboard` — Single-page metrics dashboard

Full API documentation: [docs/API.md](docs/API.md)

---

## CLI Reference

```
mosaic chat          Interactive REPL or one-shot prompt
mosaic serve         Run FastAPI server (uvicorn)
mosaic eval          Evaluate model (gates or benchmark)
mosaic guard         Run a prompt through guardrails only
mosaic config        Validate & dump resolved configuration
mosaic tools list    List registered tools
mosaic tools run     Execute a tool
mosaic train synthetic  Generate synthetic examples
mosaic train sft      Run SFT training loop
```

---

## Architecture Highlights

### StaffDecoder Pipeline
User prompt → RedSea Router (mode classification) → Exodus memory fetch (cross-attention context) → Adapter generate → Guardrail pipeline → Verifier score → (auto-escalate if stability < 0.75) → Response + ArkLedger append

### Guardrail Pipeline
Async, per-token streaming possible. Rails order: jailbreak → injection → toxicity → pii → secrets → context_window → rag_poisoning → structured_output → constitutional → factual → hallucination → rate_limit.  
Early-exit on critical severity to save cost.

### Tool Execution Flow
Tool spec → SafeToolRunner (validate target + filter env + timeout) → subprocess → output parser → ledged to ArkLedger → result returned.

---

## Writing Custom Tools

```python
from mosaic.tools.registry import registry, Tool

registry.register(Tool(
    name="my_tool",
    description="Does something useful",
    layer="utility",
    command_template=["python", "/path/to/script.py", "--arg", "{value}"],
    parameters={"value": {"type": "string", "required": True}},
    output_parser="json",
))
```

See [docs/TOOLS.md](docs/TOOLS.md).

---

## Adding New Guardrails

Subclass `Guardrail`, set `is_input`/`is_output`, implement `async def check(text, context=None) -> GuardrailResult`.

```python
from mosaic.guardrails.engine import Guardrail, GuardrailResult

class MyCustomRail(Guardrail):
    is_input = True
    async def check(self, text: str, context=None) -> GuardrailResult:
        # return GuardrailResult(name="my_rail", passed=True, score=0.0, severity="info")
        pass
```

See `src/mosaic/guardrails/` folder.

---

## Dependency Groups (pyproject.toml)

```bash
pip install -e '.[all]'         # everything
pip install -e '.[dev]'         # pytest, black, ruff, mypy, pre-commit
pip install -e '.[openai]'      # OpenAI adapter
pip install -e '.[anthropic]'   # Anthropic adapter
pip install -e '.[ollama]'      # Ollama adapter
pip install -e '.[local]'       # torch + transformers (for local models)
pip install -e '.[security]'    # structlog, defusedxml, cryptography
pip install -e '.[vision]'      # Pillow, open_clip, chromadb (for multi-modal + vector memory)
pip install -e '.[eval]'        # rouge, nltk, jiwer, code-eval
```

---

## Testing

```bash
pytest -x -s --cov=mosaic
pytest -m integration         # only integration tests
pytest --cov-report=html      # open htmlcov/index.html
```

---

## Contributing

We follow the same contribution guidelines as the upstream Moses/Setus/Aigis projects:
- Black formatting (`pre-commit run --all-files`)
- MyPy strict (`mypy src`)
- Tests for every new feature (`pytest`)
- Docstrings in Google style

See [docs/DEVELOP.md](docs/DEVELOP.md) for local setup, debugging, and architecture deep-dives.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

MOSAIC stands on the shoulders of three powerful projects:
- **Moses** — memory-first transformer architecture (Exodus, Sinai, verifier decoding)
- **Setus** — layered defense (14 OWASP rails, privacy, audit)
- **Aigis** — orchestration, multi-provider adapters, evaluation

Plus valuable patterns from **Aurelius/Cerberus** — safe tool execution, MITRE ATT&CK mapping, synthetic data generation, benchmark harness.

