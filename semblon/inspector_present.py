"""Structured Inspector sections for open media (presentation only).

Wireable fields only: file/media, when/where, observations.
Tags / ratings / map UI are omitted (DEFERRED — no schema).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semblon.memory import when_where
from semblon.product_surface import basename_path
from semblon.store import connect

__all__ = [
    "media_detail_record",
    "inspector_sections",
    "inspector_section_lines",
]


def media_detail_record(store: Path, media_id: str) -> dict[str, Any]:
    """Soft SELECT of media + observation counts. No identity writes."""
    path = Path(store)
    mid = str(media_id or "").strip()
    if not path.is_file() or not mid:
        return {}
    con = connect(path)
    try:
        row = con.execute(
            "SELECT media_id, path, source_type, width, height, mtime_ns, byte_size, sha256 "
            "FROM media WHERE media_id=?",
            (mid,),
        ).fetchone()
        if row is None:
            return {}
        faces = int(
            con.execute(
                """SELECT COUNT(*) FROM faces f
                   JOIN observations o ON o.observation_id=f.observation_id
                   WHERE o.media_id=?""",
                (mid,),
            ).fetchone()[0]
        )
        named = int(
            con.execute(
                """SELECT COUNT(*) FROM faces f
                   JOIN observations o ON o.observation_id=f.observation_id
                   WHERE o.media_id=? AND f.person_id IS NOT NULL""",
                (mid,),
            ).fetchone()[0]
        )
        obs = int(
            con.execute(
                "SELECT COUNT(*) FROM observations WHERE media_id=?", (mid,)
            ).fetchone()[0]
        )
        items = int(
            con.execute(
                """SELECT COUNT(*) FROM observation_items i
                   JOIN observations o ON o.observation_id=i.observation_id
                   WHERE o.media_id=?""",
                (mid,),
            ).fetchone()[0]
        )
    finally:
        con.close()
    rec = {
        "media_id": row["media_id"] if hasattr(row, "keys") else row[0],
        "path": row["path"] if hasattr(row, "keys") else row[1],
        "source_type": row["source_type"] if hasattr(row, "keys") else row[2],
        "width": row["width"] if hasattr(row, "keys") else row[3],
        "height": row["height"] if hasattr(row, "keys") else row[4],
        "mtime_ns": row["mtime_ns"] if hasattr(row, "keys") else row[5],
        "byte_size": row["byte_size"] if hasattr(row, "keys") else row[6],
        "sha256": row["sha256"] if hasattr(row, "keys") else row[7],
        "faces": faces,
        "named_faces": named,
        "observations": obs,
        "observation_items": items,
    }
    ww = when_where(
        str(rec.get("path") or ""),
        rec.get("mtime_ns"),
        source_type=rec.get("source_type"),
    )
    rec["when"] = ww.get("when")
    rec["when_source"] = ww.get("when_source")
    rec["folder"] = ww.get("folder")
    rec["lat"] = ww.get("lat")
    rec["lon"] = ww.get("lon")
    rec["place_source"] = ww.get("place_source")
    return rec


def inspector_sections(rec: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return section dicts that have content. Omit empty / deferred sections."""
    rec = rec or {}
    if not rec:
        return []
    sections: list[dict[str, Any]] = []
    file_lines: list[str] = []
    name = basename_path(rec.get("path"))
    if name:
        file_lines.append(name)
    folder = rec.get("folder")
    if folder:
        file_lines.append(f"Folder: {folder}")
    w, h = rec.get("width"), rec.get("height")
    if w and h:
        file_lines.append(f"Size: {int(w)} × {int(h)}")
    src = rec.get("source_type")
    if src:
        file_lines.append(f"Kind: {'video' if src == 'video' else 'photo'}")
    size = rec.get("byte_size")
    if size:
        try:
            kb = int(size) / 1024.0
            file_lines.append(f"File: {kb:,.0f} KB" if kb >= 1 else f"File: {int(size)} B")
        except (TypeError, ValueError):
            pass
    if file_lines:
        sections.append({"id": "file", "title": "File", "lines": file_lines})

    when_lines: list[str] = []
    if rec.get("when"):
        when_lines.append(str(rec["when"]))
        if rec.get("when_source"):
            when_lines.append(f"From {rec['when_source']}")
    if rec.get("lat") is not None and rec.get("lon") is not None:
        when_lines.append(f"GPS: {rec['lat']}, {rec['lon']}")
    elif folder:
        when_lines.append(f"Place cue: {folder}")
    if when_lines:
        sections.append({"id": "when_where", "title": "When / where", "lines": when_lines})

    obs_lines: list[str] = []
    faces = int(rec.get("faces") or 0)
    named = int(rec.get("named_faces") or 0)
    if faces:
        obs_lines.append(f"{faces} face{'s' if faces != 1 else ''} found")
        if named:
            obs_lines.append(f"{named} named")
        unknown = faces - named
        if unknown > 0:
            obs_lines.append(f"{unknown} unknown")
    else:
        obs_lines.append("No faces found in this photo")
    items = int(rec.get("observation_items") or 0)
    if items:
        obs_lines.append(f"{items} observation detail{'s' if items != 1 else ''}")
    obs_lines.append("Similarity is not identity.")
    sections.append({"id": "observations", "title": "Observations", "lines": obs_lines})
    return sections


def inspector_section_lines(rec: dict[str, Any] | None) -> list[str]:
    """Flat Inspector lines from structured sections (no Tags/Ratings/Map rows)."""
    sections = inspector_sections(rec)
    if not sections:
        return [
            "Photos",
            "Open a photo to explore what Semblon found.",
        ]
    lines: list[str] = []
    for sec in sections:
        if lines:
            lines.append("")
        lines.append(str(sec.get("title") or ""))
        lines.extend(str(x) for x in (sec.get("lines") or []))
    return lines
