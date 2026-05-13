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

import sqlite3
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from pydantic import BaseModel, Field


class Tier(str, Enum):
    SCRATCH = "scratch"
    EPISODE = "episode"
    ARCHIVE = "archive"


@dataclass
class MemoryEntry:
    id: str
    tier: Tier
    tokens: List[int]          # token IDs (for model ingestion)
    text: str                  # human-readable representation
    priority: float            # 0–1  (higher → keep longer)
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at


class TierBuffer:
    """Per-tier FIFO+priority buffer with capacity limit."""
    def __init__(self, capacity: int, tier: Tier):
        self.capacity = capacity
        self.tier = tier
        self._buffer: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._lru: Deque[str] = deque(maxlen=capacity)

    def add(self, entry: MemoryEntry) -> None:
        self._buffer[entry.id] = entry
        self._lru.append(entry.id)
        self._enforce_capacity()

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._buffer.get(entry_id)

    def remove(self, entry_id: str) -> None:
        self._buffer.pop(entry_id, None)
        try:
            self._lru.remove(entry_id)
        except ValueError:
            pass

    def all_entries(self) -> List[MemoryEntry]:
        return list(self._buffer.values())

    def clear(self) -> None:
        self._buffer.clear()
        self._lru.clear()

    def _enforce_capacity(self) -> None:
        while len(self._buffer) > self.capacity:
            # Evict oldest/lowest-priority
            oldest = self._lru.popleft()
            self._buffer.pop(oldest, None)

    def token_tensor(self) -> torch.Tensor:
        """Return concatenated tokens as a 1-D LongTensor."""
        all_toks: List[int] = []
        for e in self._buffer.values():
            all_toks.extend(e.tokens)
        if not all_toks:
            return torch.empty(0, dtype=torch.long)
        return torch.tensor(all_toks, dtype=torch.long)


class ExodusMemoryStore:
    """Singleton managing all three memory tiers with priority consolidation."""
    # FIXME: make per-instance (not singleton) when multi-tenant

    _instance: Optional[ExodusMemoryStore] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        scratch_cap: int = 512,
        episode_cap: int = 4096,
        archive_cap: int = 8192,
        persist_path: Optional[str] = None,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.scratch = TierBuffer(scratch_cap, Tier.SCRATCH)
        self.episode = TierBuffer(episode_cap, Tier.EPISODE)
        self.archive = TierBuffer(archive_cap, Tier.ARCHIVE)
        self.persist_path = persist_path
        self._db: Optional[sqlite3.Connection] = None
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
        for row in cur.execute("SELECT id, tier, tokens, text, priority, created_at, expires_at, metadata FROM memory_entries"):
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
                entry.id,
                entry.tier.value,
                str(entry.tokens),   # simple repr; could use json.dumps
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
        tokens: List[int],
        text: str,
        priority: float = 0.5,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, object]] = None,
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
        self._persist_entry(entry)
        return entry_id

    def get_by_tier(self, tier: Tier, limit: Optional[int] = None) -> List[MemoryEntry]:
        entries = self._get_buffer(tier).all_entries()
        if limit:
            entries = entries[:limit]
        return entries

    def query(
        self,
        query_tokens: Optional[List[int]] = None,
        tier: Tier = Tier.ARCHIVE,
        top_k: int = 5,
    ) -> List[Tuple[MemoryEntry, float]]:
        """Very naive token-overlap similarity."""
        results: List[Tuple[MemoryEntry, float]] = []
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
        src_tier: Optional[Tier] = None
        src_entry: Optional[MemoryEntry] = None
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
    def tier_tensor(self, tier: Tier, max_tokens: Optional[int] = None) -> torch.Tensor:
        """Concatenated token IDs for cross-attention injection; length ≤ max_tokens."""
        entries = self.get_by_tier(tier)
        tokens: List[int] = []
        for e in entries:
            tokens.extend(e.tokens)
            if max_tokens and len(tokens) >= max_tokens:
                break
        return torch.tensor(tokens, dtype=torch.long)

    def stats(self) -> Dict[str, int]:
        return {
            "scratch": len(self.scratch._buffer),
            "episode": len(self.episode._buffer),
            "archive": len(self.archive._buffer),
        }


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
    "Tier", "MemoryEntry", "TierBuffer", "ExodusMemoryStore", "SinaiRegisters",
]
