from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Turn:
    role: str
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    category: str = ""
    proofs: list[dict] = field(default_factory=list)


class Memory:
    """In-process conversation memory with a rolling window."""

    def __init__(self, max_turns: int = 40) -> None:
        self._turns: list[Turn] = []
        self.max_turns = max_turns

    def add(
        self,
        role: str,
        content: str,
        *,
        category: str = "",
        proofs: list[dict] | None = None,
    ) -> None:
        self._turns.append(
            Turn(role=role, content=content, category=category, proofs=proofs or [])
        )
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns :]

    def to_messages(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def history(self) -> list[dict]:
        return [
            {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp,
                "category": t.category,
                "proofs": t.proofs,
            }
            for t in self._turns
        ]

    def clear(self) -> None:
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)
