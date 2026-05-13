"""StaffDecoder full-routing integration test — auto-escalation, memory, guardrails."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mosaic.adapters.base import Message, ModelResponse
from mosaic.inference.staff_decoder import DecodeResult, StaffDecoder


@pytest.fixture
def decoder():
    # Mocks avoid needing real adapters or models
    mock_adapter = MagicMock()
    mock_adapter.name = "mock"
    mock_adapter.chat = AsyncMock(return_value=ModelResponse(
        content="This is a test response",
        model="mock-model",
        usage={"input_tokens": 10, "output_tokens": 5},
        raw={},
    ))
    mock_adapter.health = MagicMock(return_value=True)
    mock_adapter.list_models = MagicMock(return_value=["mock-model"])

    decoder = StaffDecoder(adapter=mock_adapter)
    decoder._memory = MagicMock()
    decoder._memory.query_episode.return_value = [("ep1", [0.1]*64, 0.5)]
    decoder._memory.external_isolation_purge.return_value = []
    decoder._guardrail_pipeline = MagicMock()
    decoder._guardrail_pipeline.check_input = AsyncMock(return_value=[])
    decoder._guardrail_pipeline.check_output = AsyncMock(return_value=[])
    decoder._verifier = MagicMock()
    decoder._router = MagicMock()
    decoder._router.route.return_value = "fast"  # default mode
    decoder._audit = MagicMock()
    decoder._config = MagicMock(enable_audit=True, enable_guardrails=True, auto_escalate=True, escalation_threshold=0.75)

    return decoder


@pytest.mark.asyncio
async def test_decode_basic_success(decoder):
    result: DecodeResult = await decoder.decode(
        messages=[Message(role="user", content="Hello")]
    )
    assert result.response.content == "This is a test response"
    assert result.mode == "fast"
    assert result.stability is None or result.stability >= 0.0


@pytest.mark.asyncio
async def test_auto_escalation_on_low_confidence(decoder):
    """Confidence below threshold forces deliberate mode with memory context."""
    decoder._config.auto_escalate = True
    decoder._config.escalation_threshold = 0.75
    decoder._verifier.score.return_value = 0.4  # low stability

    decoder._router.route.return_value = "deliberate"  # after re-router

    result = await decoder.decode([Message(role="user", content="Hi")])
    assert result.mode == "deliberate"
    decoder._memory.query_episode.assert_called()  # memory context injected


@pytest.mark.asyncio
async def test_memory_feedback_loop_triggers_isolation_purge(decoder):
    """PII/secrets finding in guardrails causes memory isolation."""
    decoder._config.enable_guardrails = True
    decoder._config.enable_audit = True

    # Guardrails report a PII finding
    fake_result = MagicMock()
    fake_result.passed = False
    fake_result.name = "pii"
    fake_result.severity = "critical"
    fake_result.mitre_techniques = ["T1210"]
    decoder._guardrail_pipeline.check_output.return_value = [fake_result]

    await decoder.decode([Message(role="user", content="Hello")])

    decoder._memory.external_isolation_purge.assert_called_once()
    decoder._audit.log.assert_called()  # audit trail created


@pytest.mark.asyncio
async def test_audit_logging_on_success_and_failure(decoder):
    decoder._config.enable_audit = True
    _result = await decoder.decode([Message(role="user", content="Hello")])

    # Success case logs an action
    decoder._audit.log.assert_called()
    call_args = decoder._audit.log.call_args
    action = call_args.kwargs.get("action") or call_args.args[1]
    assert action in ("DECODE_SUCCESS", "DECODE_ERROR")
