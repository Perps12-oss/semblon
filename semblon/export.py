"""Person-folder views. Originals stay put.

review.html and the Cluster Review HTML chrome are retired. The product
surface is the PySide6 shell. Review data lives on the store
(`semblon.review_board`), not in a generated page.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

# Hypothesis — clusters with min_intra below this are REVIEW REQUIRED.
STRONG_MIN_INTRA = 0.50


class ExportError(ValueError):
    pass


def _stored_json(raw):
    """Parse a SQLite JSON column only when it is valid JSON. No other rewrite."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    if not isinstance(raw, str):
        return raw
    if raw == "":
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise ExportError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


_WIN_BAD = re.compile(r'[<>:"/\\|?*]')


def _view_folder_name(display_name: str | None, person_id: str | None) -> str:
    raw = (display_name or "").strip() or (person_id or "")[:8] or "_unnamed"
    name = _WIN_BAD.sub("_", raw).strip(" .")
    return name or "_unnamed"


def _place_view(src: Path, dst: Path) -> str:
    """Hardlink if possible; copy otherwise. Never move the original."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return "exists"
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def export_views(store: Path, run_id: str, dest: Path) -> dict:
    """Person folders as views. Originals stay put. Rejected/low_quality held out."""
    dest = Path(dest)
    conn = _connect_ro(store)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ExportError(f"unknown run: {run_id}")
    rows = conn.execute(
        """
        SELECT f.face_id, f.status, f.person_id, p.display_name, m.path
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        LEFT JOIN persons p ON p.person_id = f.person_id
        WHERE f.run_id=?
        ORDER BY f.face_id
        """,
        (run_id,),
    ).fetchall()
    conn.close()

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "VIEW.txt").write_text(
        "Semblon view folder. Originals were not moved.\n"
        "Named persons get a folder. Unassigned ok faces go to _unassigned.\n"
        "rejected and low_quality are held out.\n",
        encoding="utf-8",
    )
    counts = {"persons": 0, "unassigned": 0, "held_out": 0, "missing": 0, "hardlink": 0, "copy": 0}
    seen_person: set[str] = set()
    for r in rows:
        if r["status"] != "ok":
            counts["held_out"] += 1
            continue
        src = Path(r["path"]) if r["path"] else None
        if src is None or not src.is_file():
            counts["missing"] += 1
            continue
        if r["person_id"]:
            folder = _view_folder_name(r["display_name"], r["person_id"])
            seen_person.add(r["person_id"])
        else:
            folder = "_unassigned"
            counts["unassigned"] += 1
        stem = src.stem
        ext = src.suffix or ".jpg"
        dst = dest / folder / f"{stem}__{r['face_id'][:8]}{ext}"
        how = _place_view(src, dst)
        if how in ("hardlink", "copy"):
            counts[how] += 1
    counts["persons"] = len(seen_person)
    return {
        "run_id": run_id,
        "views": str(dest.resolve()),
        "counts": counts,
        "note": "views do not move originals; cluster is not a person",
    }
