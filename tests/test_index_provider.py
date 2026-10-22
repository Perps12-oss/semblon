"""The vector index seam stays exact and SQLite-authoritative."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from semblon.index_provider import active_vector_index, index_seam_status
from semblon.observers import observe_bgr
from semblon.search import search_similar
from semblon.store import connect, init_db


def test_ann_stays_unwired():
    status = index_seam_status()
    assert status["active"] == "exact-derived"
    assert status["authoritative"] == "sqlite"
    assert status["approximate"] is False
    assert status["ann"]["enabled"] is False
    assert active_vector_index().name == "exact-derived"
    source = Path(active_vector_index.__code__.co_filename).read_text(encoding="utf-8").lower()
    assert "import faiss" not in source
    assert "import chromadb" not in source
    assert "from faiss" not in source
    assert "from chromadb" not in source


def test_search_similar_goes_through_the_index_seam(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',8,8,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',8,8,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=img, observers=("color",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='appearance'").fetchone()[0]
    conn.close()
    calls = {"n": 0}

    class _Probe:
        name = "exact-derived"

        def ready(self, _store):
            return False

        def search(self, *_args, **_kwargs):
            calls["n"] += 1
            return None

    monkeypatch.setattr("semblon.index_provider.active_vector_index", lambda: _Probe())
    rec = search_similar(store, item)
    assert calls["n"] == 1
    assert rec["status"] == "SUCCESS"
    assert rec["fallback"] == "LIBRARY_SCAN"


def _unit_index(path: Path, ids: list[str], matrix: np.ndarray) -> None:
    n = len(ids)
    labels = np.array(ids, dtype="U")
    kind = np.array(["appearance"] * n, dtype="U")
    np.savez(
        path,
        matrix=matrix.astype(np.float32),
        item_id=labels,
        kind=kind,
        provider=kind,
        modality=kind,
        pack_id=np.array(["pack-a"] * n, dtype="U"),
    )


def test_pickle_index_is_not_a_match_list(tmp_path):
    """An object-array index must not load. None sends search back to SQLite."""
    from semblon.ann_index import index_path, search_index

    store = tmp_path / "s.sqlite"
    store.write_bytes(b"")
    np.savez(
        index_path(store),
        matrix=np.zeros((1, 2), np.float32),
        item_id=np.array(["obj"], dtype=object),
    )
    found = search_index(
        store,
        item_id="obj",
        modality="appearance",
        pack_id="pack-a",
        vector=np.ones(2, np.float32).tobytes(),
        dim=2,
        limit=5,
    )
    assert found is None


def test_uncovered_query_is_none_and_a_lone_row_is_an_empty_hit_list(tmp_path):
    from semblon.ann_index import index_path, search_index

    store = tmp_path / "s.sqlite"
    store.write_bytes(b"")
    _unit_index(index_path(store), ["a"], np.array([[1.0, 0.0]], np.float32))
    kwargs = {
        "modality": "appearance",
        "pack_id": "pack-a",
        "vector": np.array([1.0, 0.0], np.float32).tobytes(),
        "dim": 2,
        "limit": 5,
    }
    assert search_index(store, item_id="missing", **kwargs) is None
    assert search_index(store, item_id="a", **kwargs) == []
    assert (
        search_index(
            store,
            item_id="a",
            modality="appearance",
            pack_id="pack-a",
            vector=np.zeros(2, np.float32).tobytes(),
            dim=2,
            limit=5,
        )
        is None
    )
    assert (
        search_index(
            store,
            item_id="a",
            modality="appearance",
            pack_id="pack-a",
            vector=np.zeros(4, np.float32).tobytes(),
            dim=4,
            limit=5,
        )
        is None
    )
