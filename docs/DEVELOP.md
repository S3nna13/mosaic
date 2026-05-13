# Developer Guide — MOSAIC

## Quickstart (10 minutes)

```bash
# Clone & enter
cd mosaic

# Create virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# Install in editable mode with all deps
pip install -e '.[all]'

# Install pre-commit hooks (optional)
pre-commit install

# Validate config
mosaic config configs/serve/local.yaml

# Run the API server
mosaic serve --reload

# In another terminal, chat
mosaic chat --prompt "What is the capital of France?" --adapter openai --model gpt-4o-mini

# Or visit the dashboard
open http://localhost:8000/dashboard
```

## Project structure

```
mosaic/
├── src/mosaic/
│   ├── model/        # Transformer + GQAAttention + MosaicTransformer
│   ├── memory/       # Exodus (3-tier) + Sinai registers
│   ├── security/     # PrivacyFilter, RateLimiter, InputGuard
│   ├── guardrails/   # 14 OWASP rails + engine
│   ├── adapters/     # OpenAI, Anthropic, Ollama, Local (HF)
│   ├── eval/         # metrics, runner, benchmarks
│   ├── inference/    # RedSea router + StaffDecoder
│   ├── orchestration/# ToolHarness + AgentSession
│   ├── audit/        # ArkLedger (hash-chain log)
│   ├── api.py        # FastAPI application
│   ├── cli.py        # Click CLI
│   └── core/         # config + Pydantic schemas
├── configs/          # YAML configs (training, serve, eval)
├── tests/            # pytest suites
├── dashboard/        # static HTML/JS UI
└── docs/             # architecture, security, config references
```

## Adding a new guardrail

1. Create `src/mosaic/guardrails/<name>.py`:

```python
from .engine import Guardrail, GuardrailResult

class MyNewGuardrail(Guardrail):
    name = "my_new_rail"
    is_input = True  # or False for output stage

    async def check(self, text: str, context: str | None = None) -> GuardrailResult:
        # Your logic here; return a GuardrailResult
        passed = True
        score = 0.0
        return GuardrailResult(name=self.name, passed=passed, score=score, severity="info")
```

2. Register in `src/mosaic/guardrails/__init__.py`:
```python
from .my_new_rail import MyNewGuardrail
ALL_RAILS.append(MyNewGuardrail)
```

3. Tune thresholds via `configs/guardrails.yaml` or env vars.

## Adding a new model adapter

Subclass `mosaic.adapters.base.BaseAdapter` and implement `chat(messages) -> ModelResponse`. Register in `adapters/__init__.py` via `build_adapter()` factory.

## Testing

```bash
pytest -x -s                # unit tests
pytest tests/unit           # specific suite
pytest --cov=mosaic         # coverage
pytest -n auto              # parallel with pytest-xdist
```

## CI / Lint

```bash
make lint   # ruff + mypy
make test   # pytest
make ci     # lint + test
```

## Configuration reference

See `docs/CONFIG.md`.

## Security policy

See `SECURITY.md` for responsible disclosure.
