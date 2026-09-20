"""Read-only library queries for the desktop workspace. No FaceKit. No identity."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from semblon.process import default_store_path, latest_run_id
from semblon.providers import weights_status

PHOTO_WINDOW = 200
PHOTO_SORTS = ("newest", "oldest", "name")


class LibraryService(Protocol):
    def home_summary(self) -> dict: ...
    def list_photos(self, *, sort: str = "newest", limit: int = PHOTO_WINDOW) -> list[dict]: ...
    def list_videos(self, *, limit: int = PHOTO_WINDOW) -> list[dict]: ...
    def list_people(self) -> list[dict]: ...
    def list_unknown(self) -> list[dict]: ...
    def list_activity(self) -> list[dict]: ...
    def settings_lines(self) -> list[str]: ...


def _connect(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _order_sql(sort: str) -> str:
    if sort == "oldest":
        return "ORDER BY COALESCE(mtime_ns, 0) ASC, path ASC"
    if sort == "name":
        return "ORDER BY path ASC"
    return "ORDER BY COALESCE(mtime_ns, 0) DESC, path ASC"


class StoreLibraryService:
    """SQLite-backed library. Pages call this on refresh; the shell owns navigation."""

    def __init__(self, store: Path | None = None) -> None:
        self.store = Path(store) if store is not None else default_store_path()

    def _available(self) -> bool:
        return self.store.is_file()

    def home_summary(self) -> dict:
        photos = self.list_photos(limit=PHOTO_WINDOW)
        videos = self.list_videos(limit=PHOTO_WINDOW)
        people = self.list_people()
        unknown = self.list_unknown()
        recent = self.list_activity()[:8]
        return {
            "photos": len(photos),
            "videos": len(videos),
            "people": len(people),
            "unknown": len(unknown),
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
        conn = _connect(self.store)
        try:
            rows = conn.execute(
                f"""SELECT media_id, path, source_type, mtime_ns
                    FROM media WHERE source_type=?
                    {_order_sql(sort)}
                    LIMIT ?""",
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

    def list_unknown(self) -> list[dict]:
        """Unnamed face groups. Cluster id is never a person id."""
        if not self._available():
            return []
        from semblon.inbox import InboxError, inbox
        from semblon.process import latest_run_id as _latest

        rid = _latest(self.store, with_faces=True)
        if rid is None:
            return []
        try:
            rec = inbox(self.store, rid)
        except InboxError:
            return []
        groups: dict[str, dict] = {}
        for it in rec.get("items") or []:
            if it.get("bucket") not in ("UNKNOWN", "REVIEW_REQUIRED"):
                continue
            cid = it.get("cluster_id")
            key = f"cluster:{cid}" if cid else f"face:{it.get('face_id')}"
            g = groups.get(key)
            if g is None:
                g = {
                    "id": key,
                    "kind": "cluster" if cid else "face",
                    "cluster_id": cid,
                    "face_id": None if cid else it.get("face_id"),
                    "label": (f"group {cid[:8]}" if cid else f"face {it.get('face_id')}"),
                    "run_id": rid,
                    "faces": 0,
                    "note": "not a person until Name",
                }
                groups[key] = g
            g["faces"] = int(g["faces"]) + 1
            if cid:
                g["face_id"] = g.get("face_id") or it.get("face_id")
        return list(groups.values())

    def list_activity(self) -> list[dict]:
        if not self._available():
            return []
        conn = _connect(self.store)
        try:
            rows = conn.execute(
                """SELECT run_id, started_at, finished_at, notes
                   FROM runs
                   ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC
                   LIMIT 40"""
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

    def settings_lines(self) -> list[str | None]:
        from semblon.observers import optional_status

        w = weights_status()
        st = optional_status()
        rid = latest_run_id(self.store, with_faces=True) if self._available() else None
        return [
            f"Store: {self.store}",
            f"Latest run with faces: {rid or 'none'}",
            "GUI must not import FaceKit.",
            "cluster ≠ person. Unknown is valid.",
            f"Weights dir: {w['dir']}",
            f"onnx files: {w['onnx_count']}  bundled={w['bundled']}",
            w.get("note"),
            f"optional ocr={st['ocr']} clip={st['clip']} pose={st['pose']}",
            st.get("identity"),
        ]
