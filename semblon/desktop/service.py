"""Read-only library queries for the desktop workspace. No FaceKit. No identity."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Protocol, TypedDict, TypeVar

from semblon.eval import DEFAULT_THRESHOLD
from semblon.inbox import _bucket
from semblon.process import default_store_path, latest_run_id
from semblon.providers import weights_status

PHOTO_WINDOW = 200
RECENT_WINDOW = 8
CACHE_TTL_S = 2.0
PHOTO_SORT_LABELS = {
    "newest": "Newest",
    "oldest": "Oldest",
    "name": "Name",
}
PHOTO_SORTS = tuple(PHOTO_SORT_LABELS)
_T = TypeVar("_T")


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
    def search_retrieval(self, *, image: Path | None = None, text: str | None = None, limit: int = 20) -> dict: ...


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

    def __init__(
        self,
        store: Path | None = None,
        *,
        cache_ttl_s: float = CACHE_TTL_S,
    ) -> None:
        self.store = Path(store) if store is not None else default_store_path()
        self.cache_ttl_s = max(float(cache_ttl_s), 0.0)
        self._cache: dict[tuple, tuple[float, object, tuple[int, int] | None]] = {}
        self._cache_lock = threading.Lock()

    def _available(self) -> bool:
        return self.store.is_file()

    def _store_signature(self) -> tuple[int, int] | None:
        if not self._available():
            return None
        try:
            st = self.store.stat()
        except OSError:
            return None
        return (int(st.st_mtime_ns), int(st.st_size))

    def invalidate(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    def _cached(
        self,
        key: tuple,
        loader: Callable[[], _T],
        *,
        ttl_s: float | None = None,
    ) -> _T:
        ttl = self.cache_ttl_s if ttl_s is None else max(float(ttl_s), 0.0)
        sig = self._store_signature()
        now = time.monotonic()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit is not None:
                ts, value, hit_sig = hit
                if hit_sig == sig and (now - ts) <= ttl:
                    return value  # type: ignore[return-value]
        value = loader()
        with self._cache_lock:
            self._cache[key] = (time.monotonic(), value, sig)
        return value

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
        def _build() -> HomeSummary:
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

        cached = self._cached(("home_summary",), _build)
        return dict(cached)

    def list_photos(self, *, sort: str = "newest", limit: int = PHOTO_WINDOW) -> list[dict]:
        if sort not in PHOTO_SORTS:
            sort = "newest"
        rows = self._cached(
            ("photos", sort, int(limit)),
            lambda: self._list_media("folder", sort=sort, limit=limit),
        )
        return list(rows)

    def list_videos(self, *, limit: int = PHOTO_WINDOW) -> list[dict]:
        rows = self._cached(
            ("videos", int(limit)),
            lambda: self._list_media("video", sort="newest", limit=limit),
        )
        return list(rows)

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
        def _load_people() -> list[dict]:
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

        rows = self._cached(("people",), _load_people)
        return list(rows)

    def _unknown_groups(self) -> list[dict]:
        """Unnamed face groups for the latest run with faces (cached by run_id)."""
        if not self._available():
            return []

        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            return []

        def _load_groups() -> list[dict]:
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
            return out

        rows = self._cached(("unknown_groups", rid), _load_groups)
        return list(rows)

    def list_unknown(self, *, limit: int = PHOTO_WINDOW) -> list[dict]:
        """Unnamed face groups. Cluster id is never a person id."""
        if limit <= 0:
            return []
        return self._unknown_groups()[: int(limit)]

    def list_activity(self, *, limit: int = 40) -> list[dict]:
        def _load_activity() -> list[dict]:
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
            try:
                from semblon.episodes import derive_episodes

                rid = latest_run_id(self.store, with_faces=True) or latest_run_id(self.store)
                if rid:
                    eps = derive_episodes(self.store, run_id=rid)
                    budget = max(0, int(limit) - len(items))
                    for ep in (eps.get("episodes") or [])[:budget]:
                        items.append(
                            {
                                "id": f"episode:{rid}:{ep.get('episode_id')}",
                                "run_id": rid,
                                "label": (
                                    f"episode {ep.get('episode_id')}  "
                                    f"tracks={ep.get('track_count', 0)}  "
                                    f"people={ep.get('people', 0)}"
                                ),
                                "kind": "episode",
                            }
                        )
            except Exception:
                # Activity remains best-effort; episodes are additive context.
                pass
            return items

        rows = self._cached(("activity", int(limit)), _load_activity)
        return list(rows)

    def settings_lines(self) -> list[str]:
        def _load_settings() -> list[str]:
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

        lines = self._cached(("settings",), _load_settings)
        return list(lines)

    def prefetch_home_async(self) -> None:
        """Best-effort cache warmup for shell navigation. Never touches Qt."""
        threading.Thread(target=self.home_summary, daemon=True).start()

    def search_retrieval(self, *, image: Path | None = None, text: str | None = None, limit: int = 20) -> dict:
        """Desktop shell hook for non-identity retrieval."""
        if image is None and not (text or "").strip():
            return {"kind": "empty", "count": 0, "items": [], "note": "query required"}
        from semblon.search import SearchError, search_image, search_text

        try:
            if image is not None:
                return search_image(self.store, image, limit=limit)
            return search_text(self.store, text or "", limit=limit)
        except SearchError as e:
            return {"kind": "error", "count": 0, "items": [], "error": str(e)}
