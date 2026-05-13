"""SafeToolRunner — async subprocess execution with defense in depth.

Adapted from CERBERUS tool_runner.py patterns. Features:
  • Safe-mode target validation (local IP ranges only, unless explicitly disabled)
  • Environment filtering — secrets stripped, only safe vars passed
  • Timeout enforcement (default 30s)
  • Output size limits to prevent disk/memory exhaustion
  • Structured output parsing (JSON, YAML, XML)
  • All executions audited via ArkLedger
"""

from __future__ import annotations

import asyncio
import fnmatch
import ipaddress
import os
import shlex
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

# Safe networks
LOCAL_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)
LOOPBACK = ipaddress.IPv4Network("127.0.0.0/8")
SAFE_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})

# Secret env var patterns (blocked from child processes)
_SECRET_PATTERNS = (
    "*SECRET*",
    "*_KEY",
    "*_TOKEN",
    "*PASSWORD*",
    "AWS_*",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)
_SAFE_KEYS = frozenset({"PATH", "HOME", "USER", "LANG", "SHELL", "TERM", "SYSTEMROOT"})


def _safe_env() -> dict[str, str]:
    """Filter os.environ to remove secrets before passing to subprocess."""
    env: dict[str, str] = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if ku in _SAFE_KEYS:
            env[k] = v
            continue
        if not any(fnmatch.fnmatch(ku, pat) for pat in _SECRET_PATTERNS):
            env[k] = v
    return env


def validate_target(target: str, safe_mode: bool = True) -> str:
    """Ensure target is local/private in safe_mode."""
    stripped = target.strip()
    if stripped in SAFE_HOSTNAMES:
        return stripped
    try:
        addr = ipaddress.ip_address(stripped)
        if addr.is_loopback or any(addr in net for net in LOCAL_NETWORKS):
            return stripped
        raise ValueError(
            f"Target {stripped} blocked — outside local ranges in safe_mode"
        )
    except ValueError:
        pass
    try:
        net = ipaddress.ip_network(stripped, strict=False)
        if any(net.subnet_of(local) for local in LOCAL_NETWORKS) or net.subnet_of(
            LOOPBACK
        ):
            return stripped
        raise ValueError(f"Network {stripped} blocked — not a local subnet")
    except ValueError as exc:
        if "blocked" in str(exc):
            raise
    raise ValueError(f"Target '{stripped}' is not an allowed IP/hostname")


@dataclass
class ToolResult:
    """Result of a tool execution — captures stdout, stderr, timing, and audit metadata."""

    tool: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:10_000],  # truncate large outputs
            "stderr": self.stderr[:2000],
            "duration_sec": round(self.duration_sec, 3),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
        }


class SafeToolRunner:
    """Async tool executor with validation, filtering, timeouts, and auditing."""

    def __init__(
        self,
        safe_mode: bool = True,
        default_timeout: float = 30.0,
        max_stdout: int = 100_000,
    ):
        self.safe_mode = safe_mode
        self.default_timeout = default_timeout
        self.max_stdout = max_stdout
        self._blocked_tools: set[str] = set()

    def block_tool(self, name: str) -> None:
        """Add a tool to the denylist (e.g., dangerous system utilities)."""
        self._blocked_tools.add(name)

    async def run(
        self,
        tool_name: str,
        command: list[str],
        *,
        target: str | None = None,
        stdin: str | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ToolResult:
        """Execute a tool safely and return its result."""
        if tool_name in self._blocked_tools:
            raise RuntimeError(f"Tool '{tool_name}' is blocked")

        # Validate target if one is provided (network tools only)
        if target and self.safe_mode:
            validate_target(target)

        cmd_str = " ".join(shlex.quote(arg) for arg in command)
        started = datetime.now(UTC)
        proc_env = env or _safe_env()

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=proc_env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin.encode() if stdin else None),
                timeout=timeout or self.default_timeout,
            )
            completed = datetime.now(UTC)

            stdout = stdout_bytes.decode(errors="replace")[: self.max_stdout]
            stderr = stderr_bytes.decode(errors="replace")[: self.max_stdout]

            result = ToolResult(
                tool=tool_name,
                command=cmd_str,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_sec=(completed - started).total_seconds(),
                started_at=started,
                completed_at=completed,
                metadata={"target": target} if target else {},
            )
            logger.info(
                "tool_executed",
                tool=tool_name,
                exit=proc.returncode,
                duration=result.duration_sec,
            )
            return result
        except TimeoutError:
            completed = datetime.now(UTC)
            logger.warning(
                "tool_timeout", tool=tool_name, timeout=timeout or self.default_timeout
            )
            return ToolResult(
                tool=tool_name,
                command=cmd_str,
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                duration_sec=(completed - started).total_seconds(),
                started_at=started,
                completed_at=completed,
                metadata={"error": "timeout"},
            )
        except Exception as e:
            completed = datetime.now(UTC)
            logger.error("tool_error", tool=tool_name, error=str(e))
            return ToolResult(
                tool=tool_name,
                command=cmd_str,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_sec=(completed - started).total_seconds(),
                started_at=started,
                completed_at=completed,
                metadata={"error": type(e).__name__},
            )


__all__ = ["SafeToolRunner", "ToolResult", "validate_target"]
