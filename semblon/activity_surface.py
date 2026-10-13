"""Activity / Memory product surface — soft history inside Home Activity.

Exposes understandable product concepts from S6 memory (people together,
moments) plus recent processing. Read-only. Never writes the store.
Never assigns persons. Time/place/co-appearance are not identity.

Product language only — no table names, person_id dumps, pack jargon, or
raw event schemas in soft output.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from semblon.empty_states import activity_empty, activity_history_lines

ACTIVITY_HEADLINE = "Recent activity"
ACTIVITY_SUBCOPY = (
    "What Semblon has noticed in your photos — "
    "recent processing, people who appear together, and moments."
)

SECTION_PROCESSING = "Recent processing"
SECTION_TOGETHER = "People together"
SECTION_MOMENTS = "Moments"

TOGETHER_EMPTY = (
    "Name people who appear in the same photos to see who was together."
)
MOMENTS_EMPTY = (
    "Moments appear after named people show up across days or folders."
)
PROCESSING_EMPTY = "Nothing processed yet. Add a photo folder to begin."

_LIMIT_TOGETHER = 8
_LIMIT_MOMENTS = 8

# Soft output must never leak these tokens (schema / identity engineering).
_LEAK_TOKENS = (
    "person_id",
    "cluster_id",
    "media_id",
    "run_id",
    "observation_groups",
    "relationships:",
    "evidence_json",
    "pack_id",
    "buffalo",
    "facekit",
    "modality=",
    "track ≠ person",
    "tracks=",
    "sqlite",
    "select ",
)


def _looks_like_id(value: Any) -> bool:
    s = str(value or "").strip()
    if not s:
        return True
    if " " in s or "-" in s and any(c.isalpha() for c in s):
        # Display names may include hyphens; bare hex-ish ids are 16+ hex chars.
        pass
    if len(s) >= 16 and all(c in "0123456789abcdefABCDEF" for c in s):
        return True
    if s.startswith("p") and len(s) > 8 and s[1:].isdigit():
        return True
    return False


def _soft_date(raw: str | None) -> str | None:
    """ISO-ish stamp → short day label. Unknown stays omitted."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    day = s[:10]
    if len(day) == 10 and day[4] == "-" and day[7] == "-":
        try:
            y, m, d = int(day[0:4]), int(day[5:7]), int(day[8:10])
            months = (
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            )
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{d} {months[m - 1]} {y}"
        except ValueError:
            return day
    return day


def _join_names(names: list[str]) -> str | None:
    clean = [n.strip() for n in names if n and not _looks_like_id(n)]
    if len(clean) < 2:
        return None
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def soft_together_line(item: dict) -> str | None:
    """One soft row for people who appear together on one photo or clip."""
    who = _join_names(list(item.get("names") or []))
    if not who:
        return None
    bits = [who]
    folder = item.get("folder")
    if folder and not _looks_like_id(folder):
        bits.append(f"in {folder}")
    when = _soft_date(item.get("when"))
    if when:
        bits.append(when)
    src = item.get("source_type")
    if src == "video":
        bits.append("video")
    return " · ".join(bits)


def soft_moment_line(ev: dict) -> str | None:
    """One soft row for a burst / day / folder signal — no LLM titles."""
    kind = (ev.get("kind") or "").strip().lower()
    folder = ev.get("folder")
    when = _soft_date(ev.get("when") or ev.get("day"))
    media = ev.get("media")
    people = ev.get("people")
    if people is None and isinstance(ev.get("person_ids"), list):
        people = len(ev["person_ids"])

    if kind == "burst":
        place = folder if folder and not _looks_like_id(folder) else "a folder"
        lead = f"Several photos in {place}"
        if isinstance(media, int) and media > 0:
            lead = f"{media} photos in {place}"
        bits = [lead]
        if when:
            bits.append(when)
        return " · ".join(bits)

    if kind == "day":
        if not when:
            return None
        bits = [when]
        if isinstance(people, int) and people > 0:
            noun = "person" if people == 1 else "people"
            bits.append(f"{people} {noun}")
        if isinstance(media, int) and media > 0:
            noun = "photo" if media == 1 else "photos"
            bits.append(f"{media} {noun}")
        return " · ".join(bits)

    if kind == "folder":
        if not folder or _looks_like_id(folder):
            return None
        bits = [folder]
        if isinstance(people, int) and people > 0:
            noun = "person" if people == 1 else "people"
            bits.append(f"{people} {noun}")
        if isinstance(media, int) and media > 0:
            noun = "photo" if media == 1 else "photos"
            bits.append(f"{media} {noun}")
        return " · ".join(bits)

    # Snapshot labels we do not understand stay out of soft product copy.
    return None


def _processing_stats(store: Path, run_id: str) -> dict[str, Any]:
    """Plain-language counts for Recent processing (no integrity jargon)."""
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        photos = int(
            conn.execute(
                "SELECT COUNT(*) FROM media "
                "WHERE source_type != 'video' OR source_type IS NULL"
            ).fetchone()[0]
        )
        run_media = conn.execute(
            """
            SELECT COUNT(DISTINCT o.media_id) AS n
            FROM observations o
            WHERE o.run_id=?
            """,
            (run_id,),
        ).fetchone()
        if run_media and int(run_media["n"] or 0) > 0:
            photos = int(run_media["n"])
        faces = int(
            conn.execute(
                "SELECT COUNT(*) FROM faces WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
        groups = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM clusters
                WHERE run_id=?
                  AND (status IS NULL OR status NOT IN ('ignored', 'merged'))
                """,
                (run_id,),
            ).fetchone()[0]
        )
        unnamed = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM clusters c
                WHERE c.run_id=?
                  AND (c.status IS NULL OR c.status NOT IN ('ignored', 'merged'))
                  AND NOT EXISTS (
                    SELECT 1 FROM faces f
                    WHERE f.cluster_id = c.cluster_id AND f.person_id IS NOT NULL
                  )
                """,
                (run_id,),
            ).fetchone()[0]
        )
        row = conn.execute(
            "SELECT finished_at, started_at FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        stamped = None
        if row is not None:
            stamped = row["finished_at"] or row["started_at"]
            if stamped:
                stamped = _soft_date(str(stamped)) or str(stamped)[:10]
    except sqlite3.OperationalError:
        return {
            "photos": None,
            "faces": None,
            "groups": None,
            "has_unnamed": False,
            "stamped": None,
        }
    finally:
        conn.close()
    return {
        "photos": photos,
        "faces": faces,
        "groups": groups,
        "has_unnamed": unnamed > 0,
        "stamped": stamped,
    }


def load_activity_memory(
    store: Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    """RO product Activity/Memory view. Empty/partial when little is ready.

    Does not invent timeline theatre. Caps row counts. Does not write.
    """
    from semblon.memory import MemoryError, events, together
    from semblon.process import latest_run_id

    p = Path(store)
    empty = {
        "empty": True,
        "partial": False,
        "processing": None,
        "together_lines": [],
        "moment_lines": [],
        "has_unnamed": False,
        "empty_state": activity_empty(),
    }
    if not p.is_file():
        return empty

    rid = run_id or latest_run_id(p)
    if not rid:
        return empty

    stats = _processing_stats(p, rid)
    processing_lines = activity_history_lines(
        photos=stats.get("photos"),
        faces=stats.get("faces"),
        groups=stats.get("groups"),
        stamped=stats.get("stamped"),
        has_unnamed=bool(stats.get("has_unnamed")),
    )

    together_lines: list[str] = []
    moment_lines: list[str] = []
    try:
        tog = together(p, run_id=rid)
        for item in (tog.get("items") or [])[: _LIMIT_TOGETHER * 2]:
            line = soft_together_line(item)
            if line and line not in together_lines:
                together_lines.append(line)
            if len(together_lines) >= _LIMIT_TOGETHER:
                break
    except MemoryError:
        tog = {"items": []}

    try:
        ev = events(p, run_id=rid)
        # Prefer bursts (concrete moments), then days, then folders.
        candidates: list[dict] = []
        for burst in ev.get("bursts") or []:
            candidates.append(dict(burst))
        for day in ev.get("days") or []:
            candidates.append(dict(day))
        for folder in ev.get("folders") or []:
            candidates.append(dict(folder))
        for item in candidates:
            line = soft_moment_line(item)
            if line and line not in moment_lines:
                moment_lines.append(line)
            if len(moment_lines) >= _LIMIT_MOMENTS:
                break
    except MemoryError:
        ev = {"bursts": [], "days": [], "folders": []}

    has_processing = bool(
        (stats.get("photos") or 0) > 0
        or (stats.get("faces") or 0) > 0
        or (stats.get("groups") or 0) > 0
    )
    has_memory = bool(together_lines or moment_lines)
    # Partial: real processing exists but memory sections are still empty.
    partial = has_processing and not has_memory

    return {
        "empty": False,
        "partial": partial,
        "processing": {
            **stats,
            "lines": processing_lines,
        },
        "together_lines": together_lines,
        "moment_lines": moment_lines,
        "has_unnamed": bool(stats.get("has_unnamed")),
        "empty_state": None,
        # Internal only — never format into soft product lines.
        "_run_id": rid,
    }


def assert_no_schema_leak(text: str) -> None:
    """Test helper / guard — soft copy must stay non-technical."""
    low = text.lower()
    for tok in _LEAK_TOKENS:
        if tok.lower() in low:
            raise AssertionError(f"schema/identity leak in soft Activity copy: {tok!r}")


def format_activity_memory_lines(view: dict[str, Any]) -> list[str]:
    """Inspector / list lines for the Activity Memory surface (soft only)."""
    if view.get("empty"):
        empty = view.get("empty_state") or activity_empty()
        return list(empty.as_lines())

    lines: list[str] = []
    proc = view.get("processing") or {}
    proc_lines = list(proc.get("lines") or [])
    if proc_lines:
        lines.append(SECTION_PROCESSING)
        lines.extend(proc_lines)
    else:
        lines.append(SECTION_PROCESSING)
        lines.append(PROCESSING_EMPTY)

    lines.append("")
    lines.append(SECTION_TOGETHER)
    together = list(view.get("together_lines") or [])
    if together:
        lines.extend(together)
    else:
        lines.append(TOGETHER_EMPTY)

    lines.append("")
    lines.append(SECTION_MOMENTS)
    moments = list(view.get("moment_lines") or [])
    if moments:
        lines.extend(moments)
    else:
        lines.append(MOMENTS_EMPTY)

    if view.get("partial") and not together and not moments:
        # Honest partial — already covered by section empties; keep one coach line.
        if view.get("has_unnamed"):
            lines.append("")
            lines.append("Start naming to grow this history.")

    return lines


def activity_workspace_sections(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Structured sections for the Activity workspace pane."""
    if view.get("empty"):
        empty = view.get("empty_state") or activity_empty()
        return [
            {
                "title": empty.headline,
                "rows": [empty.description],
                "empty": True,
            }
        ]

    sections: list[dict[str, Any]] = []
    proc = view.get("processing") or {}
    proc_rows = list(proc.get("lines") or []) or [PROCESSING_EMPTY]
    sections.append({"title": SECTION_PROCESSING, "rows": proc_rows, "empty": False})

    together = list(view.get("together_lines") or [])
    sections.append(
        {
            "title": SECTION_TOGETHER,
            "rows": together or [TOGETHER_EMPTY],
            "empty": not together,
        }
    )

    moments = list(view.get("moment_lines") or [])
    sections.append(
        {
            "title": SECTION_MOMENTS,
            "rows": moments or [MOMENTS_EMPTY],
            "empty": not moments,
        }
    )
    return sections


def read_activity_snapshot(store: Path, run_id: str) -> dict:
    """Read-only observation-graph snapshot. Not a person enrolment record."""
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        groups_rows = conn.execute(
            """
            SELECT kind, member_count, status
            FROM observation_groups
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        rel_rows = conn.execute(
            """
            SELECT kind, src_person_id, evidence_json, confirmed
            FROM relationships
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT label, t_start, t_end, folder
            FROM events
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        track_count = int(
            conn.execute("SELECT COUNT(*) FROM tracks WHERE run_id=?", (run_id,)).fetchone()[0]
        )
    finally:
        conn.close()

    groups = [dict(r) for r in groups_rows]
    relationships: list[dict] = []
    for row in rel_rows:
        rel = dict(row)
        evidence = {}
        raw = rel.get("evidence_json")
        if raw:
            try:
                evidence = json.loads(raw)
            except json.JSONDecodeError:
                evidence = {}
        rel["name_a"] = evidence.get("name_a") or evidence.get("src_name")
        rel["name_b"] = evidence.get("name_b") or evidence.get("dst_name")
        ids = evidence.get("person_ids")
        if isinstance(ids, list):
            if not rel.get("src_person_id") and len(ids) > 0:
                rel["src_person_id"] = ids[0]
            rel["other_person_ids"] = [str(i) for i in ids[1:] if i]
        else:
            rel["other_person_ids"] = []
        relationships.append(rel)

    events = [dict(r) for r in event_rows]
    return {
        "groups": groups,
        "relationships": relationships,
        "events": events,
        "track_count": track_count,
    }
