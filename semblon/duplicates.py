"""Exact duplicate integrity discovery (SHA-256).

Store schema UNIQUE(media.sha256) means content-identical files do not become
two media rows. Exact groups are found by hashing library media paths plus
sibling stills in the same directories (filesystem authority).

Near-duplicates (perceptual) are UNAVAILABLE in this slice — not fabricated.
Does not write person_id, delete files, or invent a vector DB.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from semblon.engine import _sha256_file
from semblon.ingest import STILL_EXT
from semblon.store import connect

EXACT_KIND = "exact"
NEAR_KIND = "near"
HASH_ALGORITHM = "sha256"  # SOURCE VERIFIED: semblon.engine._sha256_file / ingest

NEAR_STATUS = "UNAVAILABLE"
NEAR_REASON = (
    "Near-duplicate (perceptual) grouping is not implemented yet. "
    "Exact duplicates use SHA-256 of file bytes."
)


def library_media_rows(store: Path) -> list[dict]:
    con = connect(Path(store))
    try:
        rows = con.execute(
            "SELECT media_id, path, sha256, source_type FROM media ORDER BY path"
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        out.append(
            {
                "media_id": r["media_id"] if hasattr(r, "keys") else r[0],
                "path": r["path"] if hasattr(r, "keys") else r[1],
                "sha256": r["sha256"] if hasattr(r, "keys") else r[2],
                "source_type": r["source_type"] if hasattr(r, "keys") else r[3],
            }
        )
    return out


def scan_dirs_from_media(rows: list[dict]) -> list[Path]:
    dirs: set[Path] = set()
    for row in rows:
        p = Path(str(row.get("path") or ""))
        if not p.parts:
            continue
        parent = p.parent
        if parent and str(parent) not in {".", ""}:
            dirs.add(parent)
    return sorted(dirs, key=lambda d: str(d).lower())


def candidate_files(rows: list[dict], dirs: list[Path]) -> list[Path]:
    """Media paths plus sibling stills in those directories (not a full-drive walk)."""
    found: set[Path] = set()
    for row in rows:
        p = Path(str(row.get("path") or ""))
        if p.is_file():
            found.add(p.resolve())
    for d in dirs:
        try:
            if not d.is_dir():
                continue
            for child in d.iterdir():
                if not child.is_file():
                    continue
                if child.suffix.lower() not in STILL_EXT:
                    continue
                try:
                    found.add(child.resolve())
                except OSError:
                    continue
        except OSError:
            continue
    return sorted(found, key=lambda p: str(p).lower())


def find_exact_duplicate_groups(
    store: Path,
    *,
    want_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Group files by SHA-256. Returns only groups with 2+ members."""
    store = Path(store)
    if not store.is_file():
        return {
            "status": "ERROR",
            "reason": "Library store is unavailable.",
            "kind": EXACT_KIND,
            "hash_algorithm": HASH_ALGORITHM,
            "groups": [],
            "scanned_files": 0,
            "near_status": NEAR_STATUS,
            "near_reason": NEAR_REASON,
        }

    rows = library_media_rows(store)
    by_path = {str(Path(r["path"]).resolve()): r for r in rows if r.get("path")}
    # Also index by stored sha256 for media already hashed at ingest.
    dirs = scan_dirs_from_media(rows)
    files = candidate_files(rows, dirs)
    if not files:
        return {
            "status": "EMPTY",
            "reason": "No photos found to scan for duplicates.",
            "kind": EXACT_KIND,
            "hash_algorithm": HASH_ALGORITHM,
            "groups": [],
            "scanned_files": 0,
            "near_status": NEAR_STATUS,
            "near_reason": NEAR_REASON,
        }

    buckets: dict[str, list[dict]] = defaultdict(list)
    total = len(files)
    for i, path in enumerate(files):
        if want_cancel is not None and want_cancel():
            return {
                "status": "CANCELLED",
                "reason": "Duplicate scan cancelled.",
                "kind": EXACT_KIND,
                "hash_algorithm": HASH_ALGORITHM,
                "groups": [],
                "scanned_files": i,
                "near_status": NEAR_STATUS,
                "near_reason": NEAR_REASON,
            }
        if on_progress is not None:
            try:
                on_progress(i + 1, total)
            except Exception:  # noqa: BLE001
                pass
        key = str(path)
        media = by_path.get(key)
        digest = None
        if media and media.get("sha256"):
            digest = str(media["sha256"])
        else:
            try:
                digest = _sha256_file(path)
            except OSError:
                continue
            except Exception:  # noqa: BLE001
                continue
        buckets[digest].append(
            {
                "path": key,
                "media_id": media.get("media_id") if media else None,
                "sha256": digest,
                "in_library": bool(media),
            }
        )

    groups = []
    for digest, members in buckets.items():
        # Deduplicate by path
        uniq: dict[str, dict] = {}
        for m in members:
            uniq[m["path"]] = m
        mem = list(uniq.values())
        if len(mem) < 2:
            continue
        mem.sort(key=lambda m: (not m.get("in_library"), m["path"].lower()))
        groups.append(
            {
                "kind": EXACT_KIND,
                "hash_algorithm": HASH_ALGORITHM,
                "content_hash": digest,
                "count": len(mem),
                "members": mem,
                "media_ids": [m["media_id"] for m in mem if m.get("media_id")],
            }
        )
    groups.sort(key=lambda g: (-int(g["count"]), g["content_hash"]))

    if not groups:
        return {
            "status": "EMPTY",
            "reason": "No exact duplicate candidates were found.",
            "kind": EXACT_KIND,
            "hash_algorithm": HASH_ALGORITHM,
            "groups": [],
            "scanned_files": total,
            "near_status": NEAR_STATUS,
            "near_reason": NEAR_REASON,
        }

    return {
        "status": "SUCCESS",
        "kind": EXACT_KIND,
        "hash_algorithm": HASH_ALGORITHM,
        "groups": groups,
        "scanned_files": total,
        "group_count": len(groups),
        "near_status": NEAR_STATUS,
        "near_reason": NEAR_REASON,
    }


def group_lines(result: dict | None) -> list[str]:
    result = result or {}
    status = str(result.get("status") or "").upper()
    if status == "ERROR":
        return [result.get("reason") or "Duplicate scan failed.", "", "Your library stays open."]
    if status == "CANCELLED":
        return [result.get("reason") or "Duplicate scan cancelled."]
    if status == "EMPTY":
        lines = [
            result.get("reason") or "No exact duplicate candidates were found.",
            "",
            f"Scanned {int(result.get('scanned_files') or 0)} files (SHA-256).",
        ]
        if result.get("near_status") == NEAR_STATUS:
            lines.append("Near duplicates: unavailable.")
        return lines

    groups = list(result.get("groups") or [])
    n = len(groups)
    lines = [
        f"{n} exact duplicate group{'s' if n != 1 else ''}.",
        "",
        "Exact = same file bytes (SHA-256). Not semantic Similar.",
        "Open a group to Compare · Keep / Reject are session decisions — not delete.",
        "",
    ]
    for i, g in enumerate(groups[:12], start=1):
        mid_n = len(g.get("media_ids") or [])
        lines.append(
            f"Group {i} — {g.get('count')} files"
            + (f" ({mid_n} in library)" if mid_n else "")
        )
    if n > 12:
        lines.append(f"…and {n - 12} more groups.")
    if result.get("near_status") == NEAR_STATUS:
        lines.append("")
        lines.append("Near duplicates: unavailable in this build.")
    return lines


def open_group_lines(group: dict | None, *, index: int = 1) -> list[str]:
    group = group or {}
    members = list(group.get("members") or [])
    lines = [
        f"Duplicate group {index} — {len(members)} files",
        "",
        "Exact duplicates (SHA-256).",
        "Compare to inspect · Keep / Reject are not identity and do not delete files.",
        "",
    ]
    for m in members[:8]:
        tag = "library" if m.get("in_library") else "on disk"
        name = Path(str(m.get("path") or "")).name
        lines.append(f"  · {name} ({tag})")
    if len(members) > 8:
        lines.append(f"  …and {len(members) - 8} more.")
    return lines
