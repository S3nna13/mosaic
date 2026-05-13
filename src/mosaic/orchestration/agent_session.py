"""AgentSession — full trajectories with tool calls + audit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from mosaic.audit.ark_ledger import ArkLedger


@dataclass
class Step:
    """One step in an agent trajectory."""

    step_id: str
    prompt: str
    output: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)


class AgentSession:
    """Stateful agent session with provenance tracking."""

    def __init__(self, ledger: ArkLedger | None = None, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.ledger = ledger or ArkLedger()
        self._history: list[Step] = []

    def add_step(
        self,
        prompt: str,
        output: str,
        tool_calls: list[dict] | None = None,
        tool_results: list[Any] | None = None,
    ) -> None:
        step = Step(
            step_id=str(uuid.uuid4()),
            prompt=prompt,
            output=output,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
        )
        self._history.append(step)
        # Append to Ark Ledger for audit
        self.ledger.append(
            action={
                "type": "agent_step",
                "session_id": self.session_id,
                "step_id": step.step_id,
                "prompt": prompt[:200],
                "tools_used": [tc.get("name") for tc in (tool_calls or [])],
            },
            session_id=self.session_id,
        )

    def get_history(self) -> list[Step]:
        return list(self._history)

    def get_ledger(self) -> ArkLedger:
        return self.ledger


__all__ = [
    "AgentSession",
    "Step",
]
