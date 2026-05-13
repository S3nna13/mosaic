"""MOSAIC top-level — package root."""

from __future__ import annotations

__version__ = "0.3.0"

# Re-export core symbols for convenience
from .model.config import MosaicConfig

try:
    from .adapters import AnthropicAdapter, LocalAdapter, ModelAdapter, OpenAIAdapter  # type: ignore
    from .align import ConstitutionalRegistry, CovenantAlignment  # type: ignore
    from .api import app as fastapi_app  # type: ignore
    from .audit import ArkLedger as AuditLedger  # type: ignore
    from .cli import main as cli_main  # type: ignore
    from .eval import MosaicBenchmark  # type: ignore
    from .guardrails import ALL_RAILS, GuardrailPipeline  # type: ignore
    from .inference import ComputePolicy, InferenceMode, StaffDecoder  # type: ignore
    from .memory import ArkLedger, ExodusMemory, SinaiRegisters  # type: ignore
    from .model.transformer import MosaicForCausalLM, MosaicTransformer  # type: ignore
    from .orchestration import AgentSession, ToolHarness  # type: ignore
except ImportError:
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
    "ALL_RAILS",
    "AgentSession",
    "AnthropicAdapter",
    "ArkLedger",
    "AuditLedger",
    "ComputePolicy",
    "ConstitutionalRegistry",
    "CovenantAlignment",
    "ExodusMemory",
    "GuardrailPipeline",
    "InferenceMode",
    "LocalAdapter",
    "ModelAdapter",
    "MosaicConfig",
    "MosaicForCausalLM",
    "MosaicTransformer",
    "OpenAIAdapter",
    "SinaiRegisters",
    "StaffDecoder",
    "ToolHarness",
    "  MosaicBenchmark",
    "__version__",
    "  cli_main",
    "  fastapi_app",
]
