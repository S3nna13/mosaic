"""FastAPI application exposing MOSAIC as a production service."""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mosaic.adapters.base import Message
from mosaic.audit.ark_ledger import get_ledger
from mosaic.core.config import load_config
from mosaic.inference.staff_decoder import DecodeRequest, StaffDecoder
from mosaic.tools.registry import registry as tool_registry

logger = structlog.get_logger()

app = FastAPI(
    title="MOSAIC API",
    description="Multi-Origin Synthesis of Intelligent Capabilities — unified LLM framework",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# ── Global state ─────────────────────────────────────────────────────────────
_decoder: StaffDecoder | None = None
_metrics = {
    "requests_total": 0,
    "guardrail_blocks": 0,
    "errors_total": 0,
    "avg_latency_ms": 0.0,
    "samples": 0,
}
_start_time = time.time()


def get_decoder() -> StaffDecoder:
    global _decoder
    if _decoder is None:
        raise HTTPException(500, "Decoder not initialized — call POST /load first")
    return _decoder


# ── Request / Response models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    mode: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    guardrails: bool = True
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str
    mode_used: str
    stability: float
    request_id: str
    ts: str
    guardrail_report: list[dict] | None = None
    usage: dict | None = None


class LoadRequest(BaseModel):
    provider: str = "openai"
    model: str | None = None
    api_key: str | None = None
    path: str | None = None
    config_path: str | None = "configs/serve/local.yaml"


class StatusResponse(BaseModel):
    uptime_seconds: float
    version: str
    decoder_loaded: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/load")
async def load_model(req: LoadRequest, background_tasks: BackgroundTasks):
    global _decoder
    if _decoder is not None:
        return {"status": "already_loaded", "model": "present"}

    cfg = load_config(req.config_path)
    if req.provider:
        cfg.model.provider = req.provider
    if req.model:
        cfg.model.model = req.model
    if req.api_key:
        cfg.model.api_key = req.api_key
    if req.path:
        cfg.model.path = req.path

    try:
        _decoder = StaffDecoder(cfg)
        logger.info("decoder_loaded", provider=cfg.model.provider, model=cfg.model.model)
        return {"status": "loaded", "provider": cfg.model.provider, "model": cfg.model.model}
    except Exception as e:
        logger.error("decoder_load_failed", error=str(e))
        raise HTTPException(500, f"Failed to load model: {e}") from e


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    global _metrics
    _metrics["requests_total"] += 1
    req_start = time.time()

    decoder = get_decoder()

    messages = [Message(role=m["role"], content=m["content"]) for m in req.messages]
    mode = None
    if req.mode:
        from mosaic.inference.router import InferenceMode
        mode = InferenceMode(req.mode)

    try:
        resp = await decoder.decode(
            DecodeRequest(
                messages=messages,
                mode=mode,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
                guardrails=req.guardrails,
            )
        )
    except PermissionError as e:
        _metrics["guardrail_blocks"] += 1
        raise HTTPException(403, str(e)) from None from None
    except Exception as e:
        _metrics["errors_total"] += 1
        logger.error("decode_error", error=str(e))
        raise HTTPException(500, "Inference failed") from e

    # update latency metric
    elapsed = (time.time() - req_start) * 1000
    _metrics["samples"] += 1
    _metrics["avg_latency_ms"] = (
        _metrics["avg_latency_ms"] * (_metrics["samples"] - 1) + elapsed
    ) / _metrics["samples"]

    return ChatResponse(
        content=resp.content,
        model="mosaic",
        mode_used=resp.mode_used.value,
        stability=resp.stability,
        request_id=str(uuid.uuid4()),
        ts=datetime.now(UTC).isoformat(),
        guardrail_report=resp.guardrail_report,
        usage=resp.usage,
    )


@app.post("/guard")
async def guard_endpoint(text: str, mode: str = "input"):
    from mosaic.guardrails.engine import GuardrailPipeline
    if mode == "input":
        pipeline = GuardrailPipeline.default_input()
        results = await pipeline.check_input(text)
    else:
        pipeline = GuardrailPipeline.default_output()
        results = await pipeline.check_output(text)
    return {
        "all_passed": all(r.passed for r in results),
        "rails": [r.to_dict() for r in results],
    }


@app.get("/status", response_model=StatusResponse)
async def status():
    return StatusResponse(
        uptime_seconds=time.time() - _start_time,
        version="0.3.0",
        decoder_loaded=_decoder is not None,
    )


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus-style metrics exposition."""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
    return {
        "mosaic_requests_total": _metrics["requests_total"],
        "mosaic_guardrail_blocks_total": _metrics["guardrail_blocks"],
        "mosaic_errors_total": _metrics["errors_total"],
        "mosaic_avg_latency_ms": round(_metrics["avg_latency_ms"], 2),
    }


@app.get("/dashboard")
async def dashboard():
    decoder = _decoder
    if decoder is None:
        raise HTTPException(503, "Decoder not loaded")
    mem = decoder.memory.stats()
    guardrails_summary = getattr(decoder.guardrails, "summary", lambda: {})()
    audit = decoder.ledger.tail(5)
    return {
        "memory": mem,
        "guardrails": guardrails_summary,
        "audit_recent": [e.to_dict() for e in audit],
        "metrics": _metrics,
        "uptime_seconds": time.time() - _start_time,
    }


@app.post("/reset")
async def reset_session():
    decoder = get_decoder()
    decoder.reset_session()
    return {"status": "memory reset"}


@app.get("/audit/tail")
async def audit_tail(n: int = 20):
    ledger = get_ledger()
    entries = ledger.tail(n)
    return {"entries": [e.to_dict() for e in entries]}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    logger.info("mosaic_api_startup", version="0.3.0")







_dashboard_path = Path(__file__).parent.parent / "dashboard"
if _dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_path), html=True), name="dashboard")

@app.post("/tools/{tool_name}")
async def run_tool(tool_name: str, params: dict):
    """Execute a registered tool with the provided arguments."""
    try:
        result = await tool_registry.execute(tool_name, **params)
        return result.as_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("tool_execution_failed", tool=tool_name, error=str(e))
        raise HTTPException(500, f"Tool failed: {e}") from e


@app.get("/tools")
async def list_tools(layer: str | None = None):
    """List available tools (optionally filtered by layer)."""
    names = tool_registry.list_tools(layer=layer)
    details = []
    for name in names:
        spec = tool_registry.get(name)
        details.append({
            "name": name,
            "description": spec.description if spec else "",
            "layer": spec.layer if spec else None,
            "parameters": spec.parameters if spec else {},
        })
    return {"tools": details}


@app.post("/train/sft")
async def train_sft_endpoint(req: SFTRequest):
    """Kick off a Supervised Fine-Tune run using synthetic or provided examples."""
    try:
        adapter = build_adapter(provider=req.adapter, model=req.model, api_key=req.api_key)
        gen = SyntheticGenerator(provider=req.adapter, model=req.model, api_key=req.api_key)
        examples = None
        if req.examples:
            examples = [SyntheticExample(**ex) for ex in req.examples]
        elif req.template:
            examples = await gen.batch(req.samples or 10, req.template, **req.template_params)
        # Trainer would be configured here (stub - actual training requires GPU)
        return {"status": "started", "mode": "sft", "examples_generated": len(examples) if examples else 0}
    except Exception as e:
        logger.error("sft_failed", error=str(e))
        raise HTTPException(500, f"SFT failed: {e}") from e

__all__ = ["app"]
