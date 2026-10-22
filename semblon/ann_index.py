"""Derived exact visual index. Not an approximate nearest-neighbour index.

SQLite embeddings stay authoritative. This module writes a normalised matrix
and answers neighbours with an exact dot product (`matrix @ query`). There is
no ANN library. The historical name `ann_index` is not a claim that search is
approximate. Face vectors are excluded.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np


def index_path(store: Path) -> Path:
    return Path(str(store) + ".semblon-index.npz")


def has_index(store: Path) -> bool:
    return index_path(store).is_file()


def build_index(store: Path) -> dict:
    """Rebuild the derived index from non-face embeddings. Does not change SQLite."""
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT e.item_id, e.embedding, e.embedding_dim, e.modality, e.pack_id, i.kind, i.provider
           FROM embeddings e JOIN observation_items i ON i.item_id = e.item_id
           WHERE e.modality != 'face'"""
    ).fetchall()
    conn.close()
    ids: list[str] = []
    kinds: list[str] = []
    providers: list[str] = []
    modalities: list[str] = []
    packs: list[str] = []
    vectors: list[np.ndarray] = []
    for row in rows:
        dim = int(row["embedding_dim"])
        raw = row["embedding"]
        if raw is None or len(raw) != dim * 4:
            continue
        vec = np.frombuffer(raw, dtype=np.float32, count=dim).astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm <= 0:
            continue
        ids.append(str(row["item_id"]))
        kinds.append(str(row["kind"]))
        providers.append(str(row["provider"]))
        modalities.append(str(row["modality"]))
        packs.append(str(row["pack_id"]))
        vectors.append(vec / norm)
    path = index_path(store)
    if vectors:
        matrix = np.stack(vectors).astype(np.float32)
    else:
        matrix = np.zeros((0, 1), dtype=np.float32)
    def _labels(values: list[str]) -> np.ndarray:
        return np.array(values, dtype="U")

    np.savez(
        path,
        matrix=matrix,
        item_id=_labels(ids),
        kind=_labels(kinds),
        provider=_labels(providers),
        modality=_labels(modalities),
        pack_id=_labels(packs),
    )
    return {"path": str(path), "count": len(ids), "authoritative": "sqlite", "derived": True}


def search_index(
    store: Path,
    *,
    item_id: str,
    modality: str,
    pack_id: str,
    vector: bytes,
    dim: int,
    limit: int,
) -> list[dict] | None:
    """Neighbours from the derived index, or None when the index is absent."""
    path = index_path(store)
    if not path.is_file():
        return None
    try:
        data = np.load(path, allow_pickle=False)
    except ValueError:
        # Older indexes stored object arrays and required pickle. The file is
        # derived. SQLite stays authoritative until the next rebuild.
        return None
    matrix = np.asarray(data["matrix"], dtype=np.float32)
    ids = [str(x) for x in data["item_id"].tolist()]
    if item_id not in ids or matrix.shape[0] == 0:
        return None
    query = np.frombuffer(vector, dtype=np.float32, count=dim).astype(np.float32)
    norm = float(np.linalg.norm(query))
    if norm <= 0 or query.shape[0] != matrix.shape[1]:
        return None
    query = query / norm
    scores = matrix @ query
    modalities = [str(x) for x in data["modality"].tolist()]
    packs = [str(x) for x in data["pack_id"].tolist()]
    kinds = [str(x) for x in data["kind"].tolist()]
    providers = [str(x) for x in data["provider"].tolist()]
    order = np.argsort(-scores)
    hits = []
    for pos in order:
        i = int(pos)
        if ids[i] == item_id:
            continue
        if modalities[i] != modality or packs[i] != pack_id:
            continue
        hits.append(
            {
                "item_id": ids[i],
                "kind": kinds[i],
                "provider": providers[i],
                "score": float(scores[i]),
                "why": "derived index; same modality+pack only; not a person",
            }
        )
        if len(hits) >= limit:
            break
    return hits
