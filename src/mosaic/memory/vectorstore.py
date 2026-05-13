"""Optional vector-store memory backend — semantic search over episodic Archive.

Uses Chroma (persistent) if available; falls back to NumPy-based FAISS-style store.
Enables retrieval of semantically similar memories beyond Exodus' linear LRU.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Optional: Chroma for persistent vector DB
try:
    import chromadb

    HAVE_CHROMA = True
except ImportError:
    HAVE_CHROMA = False


# Cosine similarity helper
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = a / (np.linalg.norm(a) + 1e-8)
    b_norm = b / (np.linalg.norm(b) + 1e-8)
    return float(np.dot(a_norm, b_norm))


@dataclass
class VecEntry:
    id: str
    text: str
    embedding: np.ndarray
    metadata: dict = field(default_factory=dict)


class VectorStore:
    """Semantic memory over Exodus Archive entries."""

    def __init__(
        self,
        store_path: str = ".mosaic/vectorstore",
        use_chroma: bool = True,
        dimension: int = 2048,
    ):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.dimension = dimension
        self.entries: dict[str, VecEntry] = {}
        self._embeddings: np.ndarray | None = None  # stacked array Nbyd

        if use_chroma and HAVE_CHROMA:
            self.client = chromadb.PersistentClient(path=str(self.store_path))
            self.collection = self.client.get_or_create_collection(
                name="exodus_archive"
            )
            self._backend = "chroma"
        else:
            # Simple NumPy backend — load from disk if present
            self._backend = "numpy"
            self._load_numpy_backend()

    def _load_numpy_backend(self) -> None:
        index_path = self.store_path / "index.npz"
        if index_path.exists():
            data = np.load(index_path, allow_pickle=True)
            ids = data["ids"]
            embeddings = data["embeddings"]
            texts = data["texts"]
            metas = json.loads(data["metadatas"].item())
            for i, eid in enumerate(ids):
                self.entries[eid] = VecEntry(
                    id=eid,
                    text=texts[i],
                    embedding=embeddings[i],
                    metadata=metas.get(eid, {}),
                )
            self._embeddings = embeddings
        else:
            self.entries = {}
            self._embeddings = None

    def _save_numpy_backend(self) -> None:
        if self._backend != "numpy":
            return
        ids = list(self.entries.keys())
        embeddings = np.stack([self.entries[eid].embedding for eid in ids])
        texts = np.array([self.entries[eid].text for eid in ids], dtype=object)
        metas = json.dumps({eid: self.entries[eid].metadata for eid in ids})
        np.savez_compressed(
            self.store_path / "index.npz",
            ids=ids,
            embeddings=embeddings,
            texts=texts,
            metadatas=np.array(metas, dtype=object),
        )

    def _embed(self, text: str) -> np.ndarray:
        """Placeholder embedding function — in real usage connect to an embedding model."""
        # For now: hash-based pseudo-embedding of fixed dimension
        h = hashlib.sha256(text.encode()).digest()
        # Convert to floats in [-1,1]
        arr = np.frombuffer(h[: self.dimension * 4], dtype=np.uint8).astype(np.float32)
        return (arr / 255.0) * 2 - 1
        return arr

    def add(self, text: str, metadata: dict | None = None) -> str:
        eid = hashlib.sha1(text.encode()).hexdigest()[:16]
        embedding = self._embed(text)
        entry = VecEntry(
            id=eid, text=text, embedding=embedding, metadata=metadata or {}
        )
        self.entries[eid] = entry

        if self._backend == "chroma":
            self.collection.add(
                ids=[eid],
                embeddings=[embedding.tolist()],
                documents=[text],
                metadatas=[metadata or {}],
            )
        else:
            # NumPy backend — append to matrix
            if self._embeddings is None:
                self._embeddings = embedding[np.newaxis, :]
            else:
                self._embeddings = np.vstack([self._embeddings, embedding])
            self._save_numpy_backend()
        return eid

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float, str]]:
        q_emb = self._embed(query)
        if self._backend == "chroma":
            results = self.collection.query(
                query_embeddings=[q_emb.tolist()], n_results=top_k
            )
            return list(
                zip(
                    results["ids"][0],
                    results["distances"][0],
                    results["documents"][0],
                    strict=True,
                )
            )
        if self._embeddings is None or len(self.entries) == 0:
            return []
        sims = np.dot(self._embeddings, q_emb) / (
            np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(q_emb) + 1e-8
        )
        top_indices = np.argsort(-sims)[:top_k]
        ids = list(self.entries.keys())
        return [
            (ids[i], float(sims[i]), self.entries[ids[i]].text) for i in top_indices
        ]

    def delete(self, eid: str) -> bool:
        if eid not in self.entries:
            return False
        del self.entries[eid]
        if self._backend == "numpy":
            # rebuild matrix (inefficient, fine for small stores)
            self._rebuild_numpy_matrix()
            self._save_numpy_backend()
        else:
            self.collection.delete(ids=[eid])
        return True

    def _rebuild_numpy_matrix(self) -> None:
        if not self.entries:
            self._embeddings = None
            return
        self._embeddings = np.stack([e.embedding for e in self.entries.values()])


__all__ = ["VecEntry", "VectorStore"]
