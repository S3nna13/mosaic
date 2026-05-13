"""MOSAIC top-level — package root."""

from __future__ import annotations

__version__ = "0.3.0"

# Re-export core symbols for convenience
from .model.config import MosaicConfig
try:
    from .model.transformer import MosaicTransformer, MosaicForCausalLM  # type: ignore
    from .memory import ExodusMemory, SinaiRegisters, ArkLedger  # type: ignore
    from .inference import StaffDecoder, InferenceMode, ComputePolicy  # type: ignore
    from .align import CovenantAlignment, ConstitutionalRegistry  # type: ignore
    from .adapters import OpenAIAdapter, AnthropicAdapter, LocalAdapter, ModelAdapter  # type: ignore
    from .guardrails import GuardrailPipeline, ALL_RAILS  # type: ignore
    from .audit import ArkLedger as AuditLedger  # type: ignore
    from .orchestration import AgentSession, ToolHarness  # type: ignore
    from .eval import MosaicBenchmark  # type: ignore
    from .api import app as fastapi_app  # type: ignore
    from .cli import main as cli_main  # type: ignore
except ImportError as e:
    # Heavy optional deps (torch) may be missing; expose names anyway
    MosaicTransformer = None
    MosaicForCausalLM = None
    ExodusMemory = None
    SinaiRegisters = None
    ArkLedger = None
    StaffDecoder = None
    InferenceMode = None
    ComputePolicy = None
    CovenantAlignment = None
    ConstitutionalRegistry = None
    ModelAdapter = None
    OpenAIAdapter = None
    AnthropicAdapter = None
    LocalAdapter = None
    GuardrailPipeline = None
    ALL_RAILS = []
    AuditLedger = None
    AgentSession = None
    ToolHarness = None
    MosaicBenchmark = None
    fastapi_app = None
    cli_main = None

__all__ = [
    "__version__",
    "MosaicConfig",
    "MosaicTransformer",
    "MosaicForCausalLM",
    "ExodusMemory",
    "SinaiRegisters",
    "ArkLedger",
    "StaffDecoder",
    "InferenceMode",
    "ComputePolicy",
    "CovenantAlignment",
    "ConstitutionalRegistry",
    "ModelAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "LocalAdapter",
    "GuardrailPipeline",
    "ALL_RAILS",
    "AuditLedger",
    "AgentSession",
    "ToolHarness",
    "  MosaicBenchmark",
    "  fastapi_app",
    "  cli_main",
]
