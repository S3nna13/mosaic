"""Exodus memory tests — tiered storage, retention, consolidation, similarity."""
from __future__ import annotations

import time
import pytest
from mosaic.memory.exodus import ExodusMemoryStore, Tier, MemoryEntry


@pytest.fixture
def store():
    return ExodusMemoryStore(
        scratch_capacity=64,
        episode_capacity=256,
        archive_capacity=512,
        enable_persistence=False,
    )


def test_initial_state(store):
    assert store.size(Tier.SCRATCH) == 0
    assert store.size(Tier.EPISODE) == 0
    assert store.size(Tier.ARCHIVE) == 0


def test_write_scratch_vs_episode(store):
    token_id = 42
    vec = [0.1] * 64

    store.write(token_id, vec, tier=Tier.SCRATCH, priority=0.5)
    store.write(token_id, vec, tier=Tier.EPISODE, priority=0.9)

    assert store.size(Tier.SCRATCH) == 1
    assert store.size(Tier.EPISODE) == 1
    # Different tiers keep separate entries; same token_id OK


def test_lru_evicts_oldest_scratch_entry():
    store = ExodusMemoryStore(scratch_capacity=2)
    store.write(1, [0.1, 0.2])
    store.write(2, [0.3, 0.4])
    store.write(3, [0.5, 0.6])  # should evict token 1

    assert store.size(Tier.SCRATCH) == 2
    ids = [e.token_id for e in store._scratch_queue]
    assert 1 not in ids


def test_episode_consolidation_to_archive():
    store = ExodusMemoryStore(episode_capacity=2, archive_capacity=10)
    store.write(10, [0.1], tier=Tier.EPISODE, importance=0.9)
    store.write(11, [0.2], tier=Tier.EPISODE, importance=0.3)

    # Before consolidation: 2 in EPISODE
    assert store.size(Tier.EPISODE) == 2
    assert store.size(Tier.ARCHIVE) == 0

    store.consolidate(now=time.time() + 10_000)

    # Low-importance entry (11) should move to archive; EPISODE slot free
    assert store.size(Tier.EPISODE) == 1
    assert store.size(Tier.ARCHIVE) == 1


def test_similarity_query_returns_closest():
    store = ExodusMemoryStore(archive_capacity=100)
    ref = [1.0, 0.0]
    vec_a = [1.0, 0.1]   # cosine ~0.995
    vec_b = [0.0, 1.0]   # cosine ~0.0
    store.write("A", vec_a, tier=Tier.ARCHIVE)
    store.write("B", vec_b, tier=Tier.ARCHIVE)

    results = store.similarity_search(ref, k=1, tier=Tier.ARCHIVE)
    assert results[0].token_id == "A"


def test_persistence_roundtrip():
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "exodus.db")
        store = ExodusMemoryStore(persist_path=db, enable_persistence=True)
        store.write(99, [0.7, 0.8], tier=Tier.SCRATCH)
        store.flush()

        # Load into a fresh instance
        store2 = ExodusMemoryStore(persist_path=db, enable_persistence=True)
        assert store2.size(Tier.SCRATCH) == 1
        entry = next(iter(store2._scratch))
        assert entry.token_id == 99


def test_priority_ordering_in_scratch():
    store = ExodusMemoryStore(scratch_capacity=3)
    store.write("low1", [0.1], priority=0.1)
    store.write("high1", [0.2], priority=0.9)
    store.write("low2", [0.3], priority=0.2)

    # Order should be [high1, low2, low1] (highest-first)
    ids = [e.token_id for e in store._scratch_queue]
    assert ids[0] == "high1"
    # Scratch queue should be sorted by priority desc
    for i in range(len(store._scratch_queue) - 1):
        assert store._scratch_queue[i].priority >= store._scratch_queue[i+1].priority


def test_memory_rotation_scratch_episode():
    store = ExodusMemoryStore(scratch_capacity=2, episode_capacity=2)
    # Fill scratch
    store.write("s1", [0.1], tier=Tier.SCRATCH, priority=1.0)
    store.write("s2", [0.2], tier=Tier.SCRATCH, priority=0.9)
    # Now one more write → s1 should rotate to episode
    store.write("s3", [0.3], tier=Tier.SCRATCH, priority=0.8)
    # s1 should be in EPISODE, SCRATCH now: [s2, s3]
    scratch_ids = [e.token_id for e in store._scratch_queue]
    episode_ids = [e.token_id for e in store._episode_queue]
    assert "s1" in episode_ids
    assert "s2" in scratch_ids
    assert "s3" in scratch_ids
