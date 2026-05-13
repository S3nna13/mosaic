"""Tool harness tests — runner validation, registry, MITRE classification, audit."""
from __future__ import annotations

import pytest

from mosaic.tools.attack_mapper import MITREMapper
from mosaic.tools.registry import Tool, registry
from mosaic.tools.runner import SafeToolRunner, SecurityError, ValidationError


def test_runner_rejects_dangerous_command_by_default():
    runner = SafeToolRunner(safe_mode=True)
    with pytest.raises(SecurityError, match="disallowed"):
        runner.prepare_command("rm -rf /tmp/*")


def test_runner_allows_explicitly_allowed_tool():
    runner = SafeToolRunner(safe_mode=True, allowed_tools={"nmap"})
    cmd = runner.prepare_command("nmap -sV 127.0.0.1")
    assert "nmap" in cmd


def test_runner_env_filter_strips_sensitive_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret")
    monkeypatch.setenv("HOME", "/home/user")
    runner = SafeToolRunner(safe_mode=True)
    filtered = runner._filter_env()
    assert "OPENAI_API_KEY" not in filtered


def test_safe_mode_blocks_external_ip_by_default():
    runner = SafeToolRunner(safe_mode=True)
    with pytest.raises(ValidationError, match="external"):
        runner.prepare_command("curl https://example.com")


def test_runner_timeout_enforced():
    runner = SafeToolRunner(timeout=1)
    # Long-running command should be killed
    with pytest.raises(SecurityError, match="timeout"):
        runner.execute(["sleep", "5"])


def test_tool_registry_register_and_lookup():
    tool = Tool(
        name="test_tool",
        description="Test",
        layer="utility",
        command_template=["echo", "{msg}"],
        parameters={"msg": {"type": "string", "required": True}},
    )
    registry.register(tool)
    assert registry.get("test_tool") is tool


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        registry.get("nonexistent_tool")


def test_mitre_mapper_classifies_injection_as_t1190():
    mapper = MITREMapper()
    finding = {"reason": "Prompt contains system instruction override", "type": "injection"}
    techniques = mapper.map_finding(finding)
    ids = [t.id for t in techniques]
    assert "T1190" in ids  # Exploit Public-Facing Application


def test_mitre_mapper_fallback_to_unknown():
    mapper = MITREMapper()
    finding = {"reason": "Something completely unknown", "type": "mystery"}
    techniques = mapper.map_finding(finding)
    assert any(t.id == "T0000" for t in techniques)
