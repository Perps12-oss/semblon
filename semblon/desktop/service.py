"""Read-only library queries for the desktop workspace. No FaceKit. No identity."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol, TypedDict

from semblon.eval import DEFAULT_THRESHOLD
from semblon.inbox import _bucket
from semblon.process import default_store_path, latest_run_id
from semblon.providers import weights_status

PHOTO_WINDOW = 200
RECENT_WINDOW = 8
PHOTO_SORT_LABELS = {
    "newest": "Newest",
    "oldest": "Oldest",
    "name": "Name",
}
PHOTO_SORTS = tuple(PHOTO_SORT_LABELS)


class HomeSummary(TypedDict):
    available: bool
    photos: int
    videos: int
    people: int
    unknown: int
    recent: list[dict]
    store: str


class LibraryService(Protocol):
    def home_summary(self) -> HomeSummary: ...
    def list_photos(self, *, sort: str = "newest", limit: int = PHOTO_WINDOW) -> list[dict]: ...
    def list_videos(self, *, limit: int = PHOTO_WINDOW) -> list[dict]: ...
    def list_people(self) -> list[dict]: ...
    def list_unknown(self, *, limit: int = PHOTO_WINDOW) -> list[dict]: ...
    def list_activity(self, *, limit: int = 40) -> list[dict]: ...
    def settings_lines(self) -> list[str]: ...


def _connect(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


_ORDER_SQL_BY_SORT = {
    "newest": "ORDER BY COALESCE(mtime_ns, 0) DESC, path ASC",
    "oldest": "ORDER BY COALESCE(mtime_ns, 0) ASC, path ASC",
    "name": "ORDER BY path ASC",
}


class StoreLibraryService:
    """SQLite-backed library. Pages call this on refresh; the shell owns navigation."""

    def __init__(self, store: Path | None = None) -> None:
        self.store = Path(store) if store is not None else default_store_path()
        self._unknown_cache_run_id: str | None = None
        self._unknown_cache_groups: list[dict] = []

    def _available(self) -> bool:
        return self.store.is_file()

    def _count_media(self, source_type: str) -> int:
        if not self._available():
            return 0
        conn = _connect(self.store)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM media WHERE source_type=?",
                (source_type,),
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()

    def _count_people(self) -> int:
        if not self._available():
            return 0
        conn = _connect(self.store)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM persons WHERE status='active'"
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()

    def home_summary(self) -> HomeSummary:
        available = self._available()
        photos = self._count_media("folder")
        videos = self._count_media("video")
        people = self._count_people()
        unknown = len(self._unknown_groups())
        recent = self.list_activity(limit=RECENT_WINDOW)
        return {
            "available": available,
            "photos": photos,
            "videos": videos,
            "people": people,
            "unknown": unknown,
            "recent": recent,
            "store": str(self.store),
        }

    def list_photos(self, *, sort: str = "newest", limit: int = PHOTO_WINDOW) -> list[dict]:
        if sort not in PHOTO_SORTS:
            sort = "newest"
        return self._list_media("folder", sort=sort, limit=limit)

    def list_videos(self, *, limit: int = PHOTO_WINDOW) -> list[dict]:
        return self._list_media("video", sort="newest", limit=limit)

    def _list_media(self, source_type: str, *, sort: str, limit: int) -> list[dict]:
        if not self._available():
            return []
        order_sql = _ORDER_SQL_BY_SORT.get(sort, _ORDER_SQL_BY_SORT["newest"])
        conn = _connect(self.store)
        try:
            rows = conn.execute(
                (
                    "SELECT media_id, path, source_type, mtime_ns "
                    "FROM media WHERE source_type=? "
                    + order_sql
                    + " LIMIT ?"
                ),
                (source_type, int(limit)),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            path = r["path"] or ""
            label = Path(path).name or path
            out.append(
                {
                    "id": r["media_id"],
                    "media_id": r["media_id"],
                    "path": path,
                    "label": label,
                    "kind": "photo" if source_type == "folder" else "video",
                    "source_type": r["source_type"],
                }
            )
        return out

    def list_people(self) -> list[dict]:
        if not self._available():
            return []
        from semblon.search import SearchError, search_people

        try:
            rec = search_people(self.store)
        except SearchError:
            return []
        items = []
        for i in rec.get("items") or []:
            items.append(
                {
                    "id": i.get("person_id"),
                    "person_id": i.get("person_id"),
                    "label": i.get("display_name") or i.get("person_id"),
                    "kind": "person",
                    "faces": i.get("faces") or 0,
                }
            )
        return items

    def _unknown_groups(self) -> list[dict]:
        """Unnamed face groups for the latest run with faces (cached by run_id)."""
        if not self._available():
            return []

        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            self._unknown_cache_run_id = None
            self._unknown_cache_groups = []
            return []

        if self._unknown_cache_run_id == rid:
            return list(self._unknown_cache_groups)

        conn = _connect(self.store)
        try:
            run = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (rid,)).fetchone()
            if run is None:
                return []
            rows = conn.execute(
                """
                WITH latest_identify AS (
                    SELECT
                        d.face_id,
                        d.decision_id,
                        d.person_id AS identified_person_id,
                        d.score_top1,
                        d.score_top2,
                        d.policy_json,
                        d.created_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.face_id
                            ORDER BY d.created_at DESC, d.decision_id DESC
                        ) AS rn
                    FROM decisions d
                    WHERE d.kind='identify'
                )
                SELECT
                    f.face_id,
                    f.status,
                    f.person_id,
                    f.cluster_id,
                    li.decision_id,
                    li.identified_person_id,
                    li.score_top1,
                    li.score_top2,
                    li.policy_json,
                    li.created_at
                FROM faces f
                LEFT JOIN latest_identify li
                  ON li.face_id = f.face_id AND li.rn = 1
                WHERE f.run_id = ?
                ORDER BY f.face_id
                """,
                (rid,),
            ).fetchall()
        finally:
            conn.close()

        groups: dict[str, dict] = {}
        for r in rows:
            face = {
                "face_id": r["face_id"],
                "status": r["status"],
                "person_id": r["person_id"],
                "cluster_id": r["cluster_id"],
            }
            decision = None
            if r["decision_id"] is not None:
                decision = {
                    "decision_id": r["decision_id"],
                    "person_id": r["identified_person_id"],
                    "score_top1": r["score_top1"],
                    "score_top2": r["score_top2"],
                    "policy_json": r["policy_json"],
                    "created_at": r["created_at"],
                }
            bucket = _bucket(face, decision, DEFAULT_THRESHOLD)
            if bucket not in ("UNKNOWN", "REVIEW_REQUIRED"):
                continue
            cid = face["cluster_id"]
            key = f"cluster:{cid}" if cid else f"face:{face['face_id']}"
            g = groups.get(key)
            if g is None:
                g = {
                    "id": key,
                    "kind": "cluster" if cid else "face",
                    "cluster_id": cid,
                    "face_id": None if cid else face["face_id"],
                    "label": (f"group {cid[:8]}" if cid else f"face {face['face_id']}"),
                    "run_id": rid,
                    "faces": 0,
                    "note": "not a person until Name",
                }
                groups[key] = g
            g["faces"] = int(g["faces"]) + 1
            if cid:
                g["face_id"] = g.get("face_id") or face["face_id"]
        out = list(groups.values())
        out.sort(key=lambda rec: (-int(rec.get("faces") or 0), str(rec.get("id") or "")))
        self._unknown_cache_run_id = rid
        self._unknown_cache_groups = out
        return list(out)

    def list_unknown(self, *, limit: int = PHOTO_WINDOW) -> list[dict]:
        """Unnamed face groups. Cluster id is never a person id."""
        if limit <= 0:
            return []
        return self._unknown_groups()[: int(limit)]

    def list_activity(self, *, limit: int = 40) -> list[dict]:
        if not self._available():
            return []
        conn = _connect(self.store)
        try:
            rows = conn.execute(
                """SELECT run_id, started_at, finished_at, notes
                   FROM runs
                   ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC
                   LIMIT ?""",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        items = []
        for r in rows:
            note = r["notes"] or ("finished" if r["finished_at"] else "running")
            items.append(
                {
                    "id": r["run_id"],
                    "run_id": r["run_id"],
                    "label": f"{r['run_id']}  {note}",
                    "kind": "run",
                }
            )
        return items

    def settings_lines(self) -> list[str]:
        from semblon.observers import optional_status

        w = weights_status()
        st = optional_status()
        rid = latest_run_id(self.store, with_faces=True) if self._available() else None
        lines = [
            f"Store: {self.store}",
            f"Latest run with faces: {rid or 'none'}",
            "cluster ≠ person. Unknown is valid.",
            f"Weights dir: {w['dir']}",
            f"onnx files: {w['onnx_count']}  bundled={w['bundled']}",
            w.get("note"),
            f"optional ocr={st['ocr']} clip={st['clip']} pose={st['pose']}",
            st.get("identity"),
        ]
        return [ln for ln in lines if ln]
