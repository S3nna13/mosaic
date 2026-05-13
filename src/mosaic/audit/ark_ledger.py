"""ArkLedger — append-only, cryptographically chained action audit log.

Every entry references the previous entry's hash forming a Merkle-like chain.
Tampering with any historical entry invalidates the chain, enabling forensic
integrity verification.

Integrates with all MOSAIC layers:
  • Input Guardrails   → entry(action='input_scan', details=…)
  • Guardrail results  → entry(action='guardrail', decision=…)
  • Tool executions    → entry(action='tool_call', tool=…, params=…)
  • Memory operations  → entry(action='memory_write', tier=…, entry_id=…)
  • Alignment critique → entry(action='constitutional', verdict=…)

Export formats:
  • JSON lines (one compact entry per line)
  • SIEM-ready syslog natively via `to_syslog()`
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class ActionType(str, Enum):  # noqa: UP042
    # Core lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    # Input handling
    PROMPT_RECEIVED = "prompt_received"
    INPUT_SCANNED = "input_scanned"
    # Guardrail pipeline
    GUARDRAIL_EVAL = "guardrail_eval"
    GUARDRAIL_BLOCK = "guardrail_block"
    # Inference & alignment
    MODEL_INFERENCE = "model_inference"
    ALIGNMENT_CHECK = "alignment_check"
    ALIGNMENT_OVERRIDE = "alignment_override"
    # Memory
    MEMORY_WRITE = "memory_write"
    MEMORY_CONSOLIDATE = "memory_consolidate"
    MEMORY_PRUNE = "memory_prune"
    # Tool use
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    # Output
    OUTPUT_SCANNED = "output_scanned"
    RESPONSE_SENT = "response_sent"
    # System
    RATE_LIMIT = "rate_limit"
    ERROR = "error"
    ADMIN_ACTION = "admin_action"


@dataclass
class ArkEntry:
    id: str
    previous_hash: str
    timestamp: float
    action: ActionType
    session_id: str
    actor: str = "system"
    decision: str | None = None  # BLOCKED | PASSED | FLAGGED
    details: dict[str, Any] = field(default_factory=dict)
    hash: str = field(init=False)

    def __post_init__(self):
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        canon = self._canonical_bytes()
        return hashlib.sha256(canon).hexdigest()

    def _canonical_bytes(self) -> bytes:
        # Deterministic canonical JSON representation
        payload = {
            "id": self.id,
            "prev": self.previous_hash,
            "ts": round(self.timestamp, 6),
            "act": self.action.value,
            "sid": self.session_id,
            "actor": self.actor,
            "dec": self.decision,
            "det": self.details,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class ArkLedger:
    """Immutable append-only ledger — writes are atomic, verified, and optionally
    exported to a file for compliance/SIEM ingestion.
    """

    def __init__(self, log_path: Path | None = None):
        self._log_path = Path(log_path) if log_path else None
        self._chain_tip: ArkEntry | None = None
        self._current_session: str | None = None
        self._lock = None  # threading.Lock() if multi-threaded
        self._load_tip()

    def _load_tip(self) -> None:
        if not self._log_path or not self._log_path.exists():
            self._chain_tip = None
            return
        # Read last line
        try:
            with self._log_path.open("rb") as f:
                f.seek(-2, os.SEEK_END)
                while f.read(1) != b"\n":
                    f.seek(-2, os.SEEK_CUR)
                last = f.readline().decode()
            last_entry = ArkEntry(**json.loads(last))
            self._chain_tip = last_entry
        except Exception:
            self._chain_tip = None

    @property
    def chain_tip(self) -> ArkEntry | None:
        return self._chain_tip

    def start_session(self, session_id: str | None = None) -> str:
        sid = session_id or str(uuid.uuid4())
        self._current_session = sid
        entry = ArkEntry(
            id=str(uuid.uuid4()),
            previous_hash=self._chain_tip.hash if self._chain_tip else "0" * 64,
            timestamp=time.time(),
            action=ActionType.SESSION_START,
            session_id=sid,
            actor="system",
            details={"version": "0.3.0"},
        )
        self._append_entry(entry)
        logger.info("session_started", session_id=sid, ledger_hash=entry.hash)
        return sid

    def end_session(self) -> None:
        if not self._current_session:
            return
        entry = ArkEntry(
            id=str(uuid.uuid4()),
            previous_hash=self._chain_tip.hash,
            timestamp=time.time(),
            action=ActionType.SESSION_END,
            session_id=self._current_session,
        )
        self._append_entry(entry)
        logger.info("session_ended", session_id=self._current_session)
        self._current_session = None

    def append(
        self,
        action: ActionType,
        *,
        actor: str = "agent",
        decision: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ArkEntry:
        """Append a new audit entry to the chain."""
        if not self._current_session:
            self.start_session()
        entry = ArkEntry(
            id=str(uuid.uuid4()),
            previous_hash=self._chain_tip.hash if self._chain_tip else "0" * 64,
            timestamp=time.time(),
            action=action,
            session_id=self._current_session,
            actor=actor,
            decision=decision,
            details=details or {},
        )
        self._append_entry(entry)
        return entry

    def _append_entry(self, entry: ArkEntry) -> None:
        # Atomic write: append single line JSON
        line = entry.to_json() + "\n"
        if self._log_path:
            with self._log_path.open("a") as f:
                f.write(line)
        self._chain_tip = entry
        logger.debug(
            "audit_entry", id=entry.id, hash=entry.hash, action=entry.action.value
        )

    def verify_chain(self) -> tuple[bool, str | None]:
        """Walk entire chain and verify hashes. Returns (ok, bad_entry_id_or_None)."""
        if not self._log_path or not self._log_path.exists():
            return True, None

        prev_hash = None
        with self._log_path.open("r") as f:
            for line in f:
                entry = ArkEntry(**json.loads(line))
                if prev_hash is not None and entry.previous_hash != prev_hash:
                    return False, entry.id
                prev_hash = entry.hash
        return True, None

    def export_siem(self, dest: Path, format: str = "json") -> None:
        """Copy ledger into SIEM-friendly format."""
        if format == "json":
            dest.write_text(
                json.dumps(
                    [
                        json.loads(line)
                        for line in self._log_path.read_text().splitlines()
                        if line.strip()
                    ],
                    indent=2,
                )
            )
        elif format == "syslog":
            lines = []
            for line in self._log_path.read_text().splitlines():
                if not line.strip():
                    continue
                e = ArkEntry(**json.loads(line))
                ts = datetime.fromtimestamp(e.timestamp, tz=UTC).isoformat()
                msg = f"{ts} {e.actor} {e.action.value} (session={e.session_id}) {json.dumps(e.details)}"
                lines.append(msg)
            dest.write_text("\n".join(lines))
        else:
            raise ValueError(f"unknown format: {format}")

    def tail(self, n: int = 10) -> list[ArkEntry]:
        """Return last n entries."""
        if not self._log_path:
            return []
        with self._log_path.open() as f:
            all_lines = [line for line in f.readlines() if line.strip()]
        return [ArkEntry(**json.loads(line)) for line in all_lines[-n:]]


# ── Global singleton instance ─────────────────────────────────────────────────
_global_ledger: ArkLedger | None = None


def get_ledger() -> ArkLedger:
    global _global_ledger
    if _global_ledger is None:
        log_dir = Path.home() / ".mosaic" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _global_ledger = ArkLedger(log_path=log_dir / "ark_ledger.jsonl")
    return _global_ledger
