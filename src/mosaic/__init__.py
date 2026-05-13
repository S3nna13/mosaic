"""MOSAIC top-level — package root."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.3.0"

# core config always available
from .model.config import MosaicConfig

if TYPE_CHECKING:
    # Imported only for static type checking; at runtime these are None placeholders
    from .adapters import AnthropicAdapter, LocalAdapter, ModelAdapter, OpenAIAdapter
    from .align import ConstitutionalRegistry, CovenantAlignment
    from .api import app as fastapi_app
    from .audit import ArkLedger as AuditLedger
    from .cli import main as cli_main
    from .eval import MosaicBenchmark
    from .guardrails import ALL_RAILS, GuardrailPipeline
    from .inference import ComputePolicy, InferenceMode, StaffDecoder
    from .memory import ArkLedger, ExodusMemory, SinaiRegisters
    from .model.transformer import MosaicForCausalLM, MosaicTransformer
    from .model.verifier import VerifierHead
    from .orchestration import AgentSession, ToolHarness
else:
    # Runtime placeholders for optional heavy dependencies
    AnthropicAdapter = None
    LocalAdapter = None
    ModelAdapter = None
    OpenAIAdapter = None
    ConstitutionalRegistry = None
    CovenantAlignment = None
    fastapi_app = None
    AuditLedger = None
    cli_main = None
    MosaicBenchmark = None
    ALL_RAILS = []
    GuardrailPipeline = None
    ComputePolicy = None
    InferenceMode = None
    StaffDecoder = None
    ArkLedger = None
    ExodusMemory = None
    SinaiRegisters = None
    MosaicForCausalLM = None
    MosaicTransformer = None
    VerifierHead = None
    AgentSession = None
    ToolHarness = None

__all__ = [
    "AgentSession",
    "ALL_RAILS",
    "AnthropicAdapter",
    "ArkLedger",
    "AuditLedger",
    "cli_main",
    "ComputePolicy",
    "ConstitutionalRegistry",
    "CovenantAlignment",
    "ExodusMemory",
    "fastapi_app",
    "GuardrailPipeline",
    "InferenceMode",
    "LocalAdapter",
    "ModelAdapter",
    "MosaicBenchmark",
    "MosaicConfig",
    "MosaicForCausalLM",
    "MosaicTransformer",
    "OpenAIAdapter",
    "SinaiRegisters",
    "StaffDecoder",
    "ToolHarness",
    "VerifierHead",
]
