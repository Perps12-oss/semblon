"""Read-only Python → QML snapshot. No review mutations. No FaceKit."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot


def _default_store_path() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Semblon" / "store.sqlite"
    return Path.home() / ".local" / "share" / "semblon" / "store.sqlite"


def load_spike_snapshot(store: Path | None, run_id: str | None) -> dict:
    """Tiny RO board for the spike. Does not enrol, merge, split, or identify."""
    empty = {
        "store": "",
        "run_id": "",
        "pack_id": "",
        "status": "no-store",
        "clusters": 0,
        "unassigned": 0,
        "ok": 0,
        "persons": 0,
        "images": [],
    }
    if store is None:
        candidate = _default_store_path()
        store = candidate if candidate.is_file() else None
    if store is None or not Path(store).is_file():
        return empty
    store = Path(store).resolve()
    conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if run_id:
            run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        else:
            run = conn.execute(
                """SELECT * FROM runs
                   ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC
                   LIMIT 1"""
            ).fetchone()
        if run is None:
            return {**empty, "store": str(store), "status": "no-run"}
        rid = run["run_id"]
        ok = conn.execute(
            "SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok'", (rid,)
        ).fetchone()[0]
        clustered = conn.execute(
            """SELECT COUNT(*) FROM faces
               WHERE run_id=? AND status='ok' AND cluster_id IS NOT NULL""",
            (rid,),
        ).fetchone()[0]
        unassigned = conn.execute(
            """SELECT COUNT(*) FROM faces
               WHERE run_id=? AND status='ok' AND cluster_id IS NULL""",
            (rid,),
        ).fetchone()[0]
        clusters = conn.execute(
            "SELECT COUNT(*) FROM clusters WHERE run_id=?", (rid,)
        ).fetchone()[0]
        persons = conn.execute(
            "SELECT COUNT(*) FROM persons WHERE status='active'"
        ).fetchone()[0]
        rows = conn.execute(
            """SELECT m.path FROM faces f
               JOIN observations o ON o.observation_id = f.observation_id
               JOIN media m ON m.media_id = o.media_id
               WHERE f.run_id=? AND f.status='ok'
               ORDER BY f.face_id LIMIT 12""",
            (rid,),
        ).fetchall()
        images = []
        seen = set()
        for r in rows:
            p = r["path"]
            if p and p not in seen and Path(p).is_file():
                seen.add(p)
                images.append(Path(p).as_uri())
        return {
            "store": str(store),
            "run_id": rid,
            "pack_id": run["pack_id"] or "",
            "status": "ready",
            "clusters": int(clusters),
            "unassigned": int(unassigned),
            "ok": int(ok),
            "clustered": int(clustered),
            "persons": int(persons),
            "images": images,
        }
    finally:
        conn.close()


class ShellBridge(QObject):
    snapshotChanged = Signal()
    sectionChanged = Signal()

    def __init__(self, snapshot: dict, parent=None):
        super().__init__(parent)
        self._snap = snapshot
        self._section = "Review"
        self._sections = ["Observe", "Library", "Review", "People"]

    @Property(str, notify=snapshotChanged)
    def runId(self):
        return self._snap.get("run_id") or ""

    @Property(str, notify=snapshotChanged)
    def packId(self):
        return self._snap.get("pack_id") or ""

    @Property(str, notify=snapshotChanged)
    def status(self):
        return self._snap.get("status") or ""

    @Property(int, notify=snapshotChanged)
    def clusters(self):
        return int(self._snap.get("clusters") or 0)

    @Property(int, notify=snapshotChanged)
    def unassigned(self):
        return int(self._snap.get("unassigned") or 0)

    @Property(int, notify=snapshotChanged)
    def okFaces(self):
        return int(self._snap.get("ok") or 0)

    @Property(int, notify=snapshotChanged)
    def persons(self):
        return int(self._snap.get("persons") or 0)

    @Property("QStringList", notify=snapshotChanged)
    def images(self):
        return list(self._snap.get("images") or [])

    @Property("QStringList", constant=True)
    def sections(self):
        return list(self._sections)

    @Property(str, notify=sectionChanged)
    def section(self):
        return self._section

    @Slot(str)
    def selectSection(self, name: str) -> None:
        if name in self._sections and name != self._section:
            self._section = name
            self.sectionChanged.emit()
