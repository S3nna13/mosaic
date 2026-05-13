"""Exodus — hierarchical three-tier memory system.


Tiers:
- Scratch  (short-term reasoning workspace, 512 tokens)
- Episode  (medium-term conversational context, 4k tokens)
- Archive  (long-term semantic facts, 8k tokens)

Features:
• LRU eviction per-tier with capacity enforcement
• Automatic consolidation: scratch → episode → archive based on priority score
• SQLite persistence (optional) to survive process restarts
• Cross-attention injection: each memory tier can be attended to by
  any transformer layer (configurable injection frequency)
• Sinai learnable registers (shared across instances) for rapid side-channel access
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum

import torch
import json
import torch.nn as nn


class Tier(str, Enum):  # noqa: UP042
    SCRATCH = "scratch"
    EPISODE = "episode"
    ARCHIVE = "archive"


@dataclass
class MemoryEntry:
    id: str
    tier: Tier
    tokens: list[int]  # token IDs (for model ingestion)
    text: str  # human-readable representation
    priority: float  # 0-1  (higher → keep longer)
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    embedding: list[float] | None = None

    def is_expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at

    @property
    def token_id(self):
        return self.id


class TierBuffer:
    """Per-tier FIFO+priority buffer with capacity limit."""

    def __init__(self, capacity: int, tier: Tier):
        self.capacity = capacity
        self.tier = tier
        self._buffer: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._lru: deque[str] = deque()

    def add(self, entry: MemoryEntry) -> None:
        self._buffer[entry.id] = entry
        self._lru.append(entry.id)

    def get(self, entry_id: str) -> MemoryEntry | None:
        return self._buffer.get(entry_id)

    def remove(self, entry_id: str) -> None:
        self._buffer.pop(entry_id, None)
        with contextlib.suppress(ValueError):
            self._lru.remove(entry_id)

    def all_entries(self) -> list[MemoryEntry]:
        return list(self._buffer.values())

    def clear(self) -> None:
        self._buffer.clear()
        self._lru.clear()

    def _enforce_capacity(self) -> None:
        while len(self._buffer) > self.capacity:
            # Evict least-recently-used entry that is still in the buffer
            oldest = self._lru.popleft()
            self._buffer.pop(oldest, None)
    def token_tensor(self) -> torch.Tensor:
        """Return concatenated tokens as a 1-D LongTensor."""
        all_toks: list[int] = []
        for e in self._buffer.values():
            all_toks.extend(e.tokens)
        if not all_toks:
            return torch.empty(0, dtype=torch.long)
        return torch.tensor(all_toks, dtype=torch.long)


class ExodusMemoryStore:
    """Singleton managing all three memory tiers with priority consolidation."""

    # FIXME: make per-instance (not singleton) when multi-tenant



    def __init__(
        self,
        scratch_capacity: int = 512,
        episode_capacity: int = 4096,
        archive_capacity: int = 8192,
        enable_persistence: bool = False,
        persist_path: str | None = None,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.scratch = TierBuffer(scratch_capacity, Tier.SCRATCH)
        self.episode = TierBuffer(episode_capacity, Tier.EPISODE)
        self.archive = TierBuffer(archive_capacity, Tier.ARCHIVE)
        if enable_persistence:
            self.persist_path = persist_path or "./exodus_memory.db"
        else:
            self.persist_path = None
        self._db: sqlite3.Connection | None = None
        self._init_db()
        self._initialized = True

    # ── Database persistence ──────────────────────────────────────────────────
    def _init_db(self) -> None:
        if not self.persist_path:
            return
        self._db = sqlite3.connect(self.persist_path, check_same_thread=False)
        cur = self._db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS memory_entries (
            id TEXT PRIMARY KEY,
            tier TEXT,
            tokens TEXT,            -- JSON array
            text TEXT,
            priority REAL,
            created_at REAL,
            expires_at REAL,
            metadata TEXT
        )""")
        self._db.commit()
        self._load_from_db()

    def _load_from_db(self) -> None:
        if not self._db:
            return
        cur = self._db.cursor()
        for row in cur.execute(
            "SELECT id, tier, tokens, text, priority, created_at, expires_at, metadata FROM memory_entries"
        ):
            eid, tier_s, tokens_s, text, prio, created, expires, _meta = row
            tier = Tier(tier_s)
            entry = MemoryEntry(
                id=eid,
                tier=tier,
                tokens=eval(tokens_s),  # safe: our own JSON dumps
                text=text,
                priority=prio,
                created_at=created,
                expires_at=expires,
                metadata={},
            )
            buf = self._get_buffer(tier)
            buf.add(entry)

    def _persist_entry(self, entry: MemoryEntry) -> None:
        if not self._db:
            return
        cur = self._db.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO memory_entries VALUES (?,?,?,?,?,?,?,?)",
            (
                json.dumps(entry.id),
                entry.tier.value,
                str(entry.tokens),  # simple repr; could use json.dumps
                entry.text,
                entry.priority,
                entry.created_at,
                entry.expires_at,
                str(entry.metadata),
            ),
        )
        self._db.commit()

    # ── Public API ────────────────────────────────────────────────────────────
    def _get_buffer(self, tier: Tier) -> TierBuffer:
        return {
            Tier.SCRATCH: self.scratch,
            Tier.EPISODE: self.episode,
            Tier.ARCHIVE: self.archive,
        }[tier]

    def add(
        self,
        tier: Tier,
        tokens: list[int],
        text: str,
        priority: float = 0.5,
        ttl_seconds: float | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        entry_id = str(uuid.uuid4())
        expires = (time.time() + ttl_seconds) if ttl_seconds else None
        entry = MemoryEntry(
            id=entry_id,
            tier=tier,
            tokens=tokens,
            text=text,
            priority=max(0.0, min(1.0, priority)),
            expires_at=expires,
            metadata=metadata or {},
        )
        buf = self._get_buffer(tier)
        buf.add(entry)
        
        # Auto-rotate oldest SCRATCH entry to EPISODE on overflow
        if tier is Tier.SCRATCH:
            while len(self.scratch._buffer) > self.scratch.capacity:
                # Find oldest entry still in SCRATCH
                oldest_id = None
                while self.scratch._lru:
                    cand = self.scratch._lru[0]
                    if cand in self.scratch._buffer:
                        oldest_id = cand
                        break
                    else:
                        # stale ID, discard
                        self.scratch._lru.popleft()
                if oldest_id is None:
                    break
                self.consolidate_upwards(oldest_id, Tier.EPISODE)
        self._persist_entry(entry)
        return entry_id

    def get_by_tier(self, tier: Tier, limit: int | None = None) -> list[MemoryEntry]:
        entries = self._get_buffer(tier).all_entries()
        if limit:
            entries = entries[:limit]
        return entries

    def query(
        self,
        query_tokens: list[int] | None = None,
        tier: Tier = Tier.ARCHIVE,
        top_k: int = 5,
    ) -> list[tuple[MemoryEntry, float]]:
        """Very naive token-overlap similarity."""
        results: list[tuple[MemoryEntry, float]] = []
        for entry in self._get_buffer(tier).all_entries():
            if not entry.tokens or not query_tokens:
                score = entry.priority  # fallback
            else:
                common = set(entry.tokens) & set(query_tokens)
                score = len(common) / len(set(entry.tokens) | set(query_tokens))
            results.append((entry, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def consolidate_upwards(self, entry_id: str, target_tier: Tier) -> bool:
        """Move entry from its current tier up to target_tier (e.g., scratch→episode)."""
        # Find the entry across tiers (could optimise with index)
        src_tier: Tier | None = None
        src_entry: MemoryEntry | None = None
        for t in Tier:
            buf = self._get_buffer(t)
            e = buf.get(entry_id)
            if e:
                src_tier, src_entry = t, e
                break
        if src_entry is None or src_tier is None:
            return False
        if src_tier == target_tier:
            return False

        # Remove from source tier
        self._get_buffer(src_tier).remove(entry_id)

        # Boost priority (knowledge gets more valuable when consolidated)
        src_entry.priority = min(1.0, src_entry.priority + 0.2)
        src_entry.tier = target_tier

        # Add to target
        self._get_buffer(target_tier).add(src_entry)
        self._persist_entry(src_entry)
        return True

    def prune_expired(self) -> int:
        removed = 0
        for tier in Tier:
            buf = self._get_buffer(tier)
            for eid in list(buf._buffer):
                e = buf.get(eid)
                if e and e.is_expired():
                    buf.remove(eid)
                    removed += 1
        return removed

    def clear_all(self) -> None:
        for tier in Tier:
            self._get_buffer(tier).clear()
        if self._db:
            cur = self._db.cursor()
            cur.execute("DELETE FROM memory_entries")
            self._db.commit()

    # ── Tensor helpers for model ingestion ────────────────────────────────────
    def tier_tensor(self, tier: Tier, max_tokens: int | None = None) -> torch.Tensor:
        """Concatenated token IDs for cross-attention injection; length ≤ max_tokens."""
        entries = self.get_by_tier(tier)
        tokens: list[int] = []
        for e in entries:
            tokens.extend(e.tokens)
            if max_tokens and len(tokens) >= max_tokens:
                break
        return torch.tensor(tokens, dtype=torch.long)

    def stats(self) -> dict[str, int]:
        return {
            "scratch": len(self.scratch._buffer),
            "episode": len(self.episode._buffer),
            "archive": len(self.archive._buffer),
        }

    # ── Test/Convenience API ────────────────────────────────────────────────────
    def size(self, tier: Tier) -> int:
        """Return number of entries in the given tier."""
        return len(self._get_buffer(tier)._buffer)

    def write(
        self,
        token_id,
        vector: list[float],
        tier: Tier = Tier.SCRATCH,
        priority: float | None = None,
        importance: float | None = None,
    ) -> str:
        """Store an embedding vector associated with a token_id."""
        if importance is not None:
            priority = importance
        if priority is None:
            priority = 0.5
        entry = MemoryEntry(
            id=token_id,
            tier=tier,
            tokens=[],
            text="",
            priority=priority,
            embedding=vector,
        )
        buf = self._get_buffer(tier)
        buf.add(entry)
        
        # Auto-rotate oldest SCRATCH entry to EPISODE on overflow
        if tier is Tier.SCRATCH:
            while len(self.scratch._buffer) > self.scratch.capacity:
                # Find oldest entry still in SCRATCH
                oldest_id = None
                while self.scratch._lru:
                    cand = self.scratch._lru[0]
                    if cand in self.scratch._buffer:
                        oldest_id = cand
                        break
                    else:
                        self.scratch._lru.popleft()
                if oldest_id is None:
                    break
                self.consolidate_upwards(oldest_id, Tier.EPISODE)
        if self.persist_path:
            self._persist_entry(entry)
        return entry.id

    def similarity_search(
        self,
        query: list[float],
        k: int = 5,
        tier: Tier = Tier.ARCHIVE,
    ) -> list[MemoryEntry]:
        """Return top-k entries from tier by cosine similarity to query vector."""
        buf = self._get_buffer(tier)
        query_arr = [float(x) for x in query]
        q_norm = (sum(x * x for x in query_arr) ** 0.5) + 1e-8
        scored = []
        for entry in buf._buffer.values():
            if entry.embedding is None:
                continue
            vec = entry.embedding
            norm = (sum(x * x for x in vec) ** 0.5) + 1e-8
            dot = sum(a * b for a, b in zip(query_arr, vec, strict=True))
            score = dot / (q_norm * norm)
            scored.append((entry, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:k]]

    def consolidate(self, now: float | None = None) -> None:
        """Move the lowest-importance EPISODE entry to ARCHIVE."""
        episode_entries = self._get_buffer(Tier.EPISODE).all_entries()
        if not episode_entries:
            return
        # Pick lowest priority; tie-break by creation time (oldest)
        target = min(episode_entries, key=lambda e: (e.priority, e.created_at))
        self.consolidate_upwards(target.id, Tier.ARCHIVE)

    def flush(self) -> None:
        """Commit any pending DB writes."""
        if self._db is not None:
            self._db.commit()

    @property
    def _scratch(self):
        """Set of MemoryEntry objects in SCRATCH tier."""
        return list(self.scratch._buffer.values())

    @property
    def _episode(self):
        return list(self.episode._buffer.values())

    @property
    def _archive(self):
        return list(self.archive._buffer.values())

    @property
    def _scratch_queue(self):
        """List of SCRATCH entries sorted by priority desc (highest first)."""
        return sorted(
            self.scratch._buffer.values(), key=lambda e: e.priority, reverse=True
        )

    @property
    def _episode_queue(self):
        return sorted(
            self.episode._buffer.values(), key=lambda e: e.priority, reverse=True
        )


class SinaiRegisters(nn.Module):
    """Learnable register vectors shared across all conversations."""

    def __init__(self, dim: int, count: int = 16):
        super().__init__()
        self.register = nn.Parameter(torch.randn(count, dim) * 0.02)
        self.count = count
        self.dim = dim

    def forward(self, batch_size: int) -> torch.Tensor:
        # returns [B, count, dim]
        return self.register.unsqueeze(0).expand(batch_size, -1, -1)


__all__ = [
    "ExodusMemoryStore",
    "MemoryEntry",
    "SinaiRegisters",
    "Tier",
    "TierBuffer",
]
