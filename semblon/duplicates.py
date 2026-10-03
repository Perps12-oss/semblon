"""Integrity similarity (A): exact SHA-256 + perceptual near-duplicates.

Exact groups hash library media paths plus sibling stills (filesystem authority).
Near groups use OpenCV aHash/dHash + Hamming — ephemeral scan, no schema.

Does not write person_id, delete files, or invent a vector DB.
Find Similar (C) and search_similar (B) are separate stacks — never reused here.
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
NEAR_HASH_ALGORITHM = "ahash+dhash"

# 64-bit hashes; Hamming ≤ threshold groups as near. Tuned for aggressive fixtures
# (same/recompress/resize/crop/bright ≤ 14; visually-similar-but-different ≈ 21+).
NEAR_HAMMING_THRESHOLD = 14

NEAR_STATUS_AVAILABLE = "AVAILABLE"
NEAR_STATUS_UNAVAILABLE = "UNAVAILABLE"
# Backward-compatible alias used by older exact-only tests.
NEAR_STATUS = NEAR_STATUS_AVAILABLE
NEAR_REASON = (
    "Near-duplicate (perceptual) grouping uses OpenCV aHash/dHash + Hamming. "
    "Exact duplicates use SHA-256 of file bytes. Not Find Similar / search_similar."
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


def _empty_exact(status: str, reason: str, *, scanned: int = 0) -> dict:
    return {
        "status": status,
        "reason": reason,
        "kind": EXACT_KIND,
        "hash_algorithm": HASH_ALGORITHM,
        "groups": [],
        "scanned_files": scanned,
        "near_status": NEAR_STATUS_AVAILABLE,
        "near_reason": NEAR_REASON,
    }


def find_exact_duplicate_groups(
    store: Path,
    *,
    want_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Group files by SHA-256. Returns only groups with 2+ members."""
    store = Path(store)
    if not store.is_file():
        return _empty_exact("ERROR", "Library store is unavailable.")

    rows = library_media_rows(store)
    by_path = {str(Path(r["path"]).resolve()): r for r in rows if r.get("path")}
    dirs = scan_dirs_from_media(rows)
    files = candidate_files(rows, dirs)
    if not files:
        return _empty_exact("EMPTY", "No photos found to scan for duplicates.")

    buckets: dict[str, list[dict]] = defaultdict(list)
    total = len(files)
    for i, path in enumerate(files):
        if want_cancel is not None and want_cancel():
            return _empty_exact("CANCELLED", "Duplicate scan cancelled.", scanned=i)
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
        return _empty_exact(
            "EMPTY", "No exact duplicate candidates were found.", scanned=total
        )

    return {
        "status": "SUCCESS",
        "kind": EXACT_KIND,
        "hash_algorithm": HASH_ALGORITHM,
        "groups": groups,
        "scanned_files": total,
        "group_count": len(groups),
        "near_status": NEAR_STATUS_AVAILABLE,
        "near_reason": NEAR_REASON,
    }


def _load_gray(path: Path):
    """Load grayscale BGR→gray via OpenCV. Returns None if unavailable."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    except Exception:  # noqa: BLE001
        return None
    if img is None or getattr(img, "size", 0) == 0:
        return None
    return img


def ahash64(gray) -> int:
    """Average hash — 8×8 → 64-bit int."""
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    flat = small.astype(np.float64).ravel()
    avg = float(flat.mean())
    bits = 0
    for i, v in enumerate(flat):
        if v >= avg:
            bits |= 1 << i
    return int(bits)


def dhash64(gray) -> int:
    """Difference hash — 9×8 adjacent compare → 64-bit int."""
    import cv2  # type: ignore

    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = 0
    bit_i = 0
    for y in range(8):
        for x in range(8):
            if int(small[y, x + 1]) >= int(small[y, x]):
                bits |= 1 << bit_i
            bit_i += 1
    return int(bits)


def hamming64(a: int, b: int) -> int:
    return int((int(a) ^ int(b)).bit_count())


def perceptual_distance(gray_a, gray_b) -> int:
    """Max Hamming of aHash and dHash (conservative near-dup distance)."""
    return max(
        hamming64(ahash64(gray_a), ahash64(gray_b)),
        hamming64(dhash64(gray_a), dhash64(gray_b)),
    )


def _union_find_groups(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in edges:
        union(a, b)
    buckets: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        buckets[find(i)].append(i)
    return [sorted(v) for v in buckets.values() if len(v) >= 2]


def find_near_duplicate_groups(
    store: Path,
    *,
    threshold: int = NEAR_HAMMING_THRESHOLD,
    want_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Group library stills by perceptual hash Hamming distance.

    Ephemeral — no schema. OpenCV required; honest UNAVAILABLE otherwise.
    """
    store = Path(store)
    if not store.is_file():
        return {
            "status": "ERROR",
            "reason": "Library store is unavailable.",
            "kind": NEAR_KIND,
            "hash_algorithm": NEAR_HASH_ALGORITHM,
            "threshold": int(threshold),
            "groups": [],
            "scanned_files": 0,
        }

    try:
        import cv2  # noqa: F401  # type: ignore
        import numpy as np  # noqa: F401  # type: ignore
    except ImportError:
        return {
            "status": "UNAVAILABLE",
            "reason": "OpenCV is required for near-duplicate (perceptual) grouping.",
            "kind": NEAR_KIND,
            "hash_algorithm": NEAR_HASH_ALGORITHM,
            "threshold": int(threshold),
            "groups": [],
            "scanned_files": 0,
        }

    rows = [
        r
        for r in library_media_rows(store)
        if (r.get("source_type") or "") != "video" and r.get("path")
    ]
    entries: list[dict] = []
    hashes: list[tuple[int, int]] = []
    total = len(rows)
    for i, row in enumerate(rows):
        if want_cancel is not None and want_cancel():
            return {
                "status": "CANCELLED",
                "reason": "Near-duplicate scan cancelled.",
                "kind": NEAR_KIND,
                "hash_algorithm": NEAR_HASH_ALGORITHM,
                "threshold": int(threshold),
                "groups": [],
                "scanned_files": i,
            }
        if on_progress is not None:
            try:
                on_progress(i + 1, total)
            except Exception:  # noqa: BLE001
                pass
        path = Path(str(row["path"]))
        gray = _load_gray(path)
        if gray is None:
            continue
        try:
            ah = ahash64(gray)
            dh = dhash64(gray)
        except Exception:  # noqa: BLE001
            continue
        entries.append(
            {
                "path": str(path.resolve()) if path.is_file() else str(path),
                "media_id": row.get("media_id"),
                "in_library": True,
            }
        )
        hashes.append((ah, dh))

    n = len(entries)
    if n < 2:
        return {
            "status": "EMPTY",
            "reason": "Not enough photos to compare for near duplicates.",
            "kind": NEAR_KIND,
            "hash_algorithm": NEAR_HASH_ALGORITHM,
            "threshold": int(threshold),
            "groups": [],
            "scanned_files": total,
        }

    edges: list[tuple[int, int]] = []
    for i in range(n):
        ai, di = hashes[i]
        for j in range(i + 1, n):
            aj, dj = hashes[j]
            dist = max(hamming64(ai, aj), hamming64(di, dj))
            if dist <= int(threshold):
                edges.append((i, j))

    clusters = _union_find_groups(n, edges)
    groups = []
    for idxs in clusters:
        mem = [entries[k] for k in idxs]
        mem.sort(key=lambda m: (not m.get("in_library"), str(m.get("path") or "").lower()))
        # Representative hash of first member for stable ordering.
        ah0, dh0 = hashes[idxs[0]]
        groups.append(
            {
                "kind": NEAR_KIND,
                "hash_algorithm": NEAR_HASH_ALGORITHM,
                "content_hash": f"{ah0:016x}:{dh0:016x}",
                "count": len(mem),
                "members": mem,
                "media_ids": [m["media_id"] for m in mem if m.get("media_id")],
                "threshold": int(threshold),
            }
        )
    groups.sort(key=lambda g: (-int(g["count"]), g["content_hash"]))

    if not groups:
        return {
            "status": "EMPTY",
            "reason": "No near-duplicate candidates were found.",
            "kind": NEAR_KIND,
            "hash_algorithm": NEAR_HASH_ALGORITHM,
            "threshold": int(threshold),
            "groups": [],
            "scanned_files": total,
            "group_count": 0,
        }

    return {
        "status": "SUCCESS",
        "kind": NEAR_KIND,
        "hash_algorithm": NEAR_HASH_ALGORITHM,
        "threshold": int(threshold),
        "groups": groups,
        "scanned_files": total,
        "group_count": len(groups),
    }


def find_integrity_groups(store: Path, **kwargs) -> dict:
    """Combined Exact + Near integrity scan for Home Duplicates surface."""
    exact = find_exact_duplicate_groups(store, **kwargs)
    near = find_near_duplicate_groups(store, **kwargs)
    return {
        "status": exact.get("status") if exact.get("groups") else near.get("status") or exact.get("status"),
        "exact": exact,
        "near": near,
        "kind": "integrity",
        "groups": list(exact.get("groups") or []) + list(near.get("groups") or []),
        "exact_group_count": int(exact.get("group_count") or len(exact.get("groups") or [])),
        "near_group_count": int(near.get("group_count") or len(near.get("groups") or [])),
        "near_status": near.get("status") or NEAR_STATUS_AVAILABLE,
        "near_reason": NEAR_REASON,
        "hash_algorithm": HASH_ALGORITHM,
        "scanned_files": max(
            int(exact.get("scanned_files") or 0), int(near.get("scanned_files") or 0)
        ),
    }


def similarity_basis_label(kind: str | None) -> str:
    """A/B/C product labels — do not collapse stacks."""
    k = (kind or "").strip().lower()
    return {
        "exact": "Exact (file bytes · SHA-256)",
        "near": "Near match (looks alike · aHash/dHash)",
        "similar": "Whole photo (image-to-image)",
        "whole": "Whole photo (image-to-image)",
        "region": "Selected region",
        "find_similar": "Selected region",
    }.get(k, "Similarity")


def group_lines(result: dict | None) -> list[str]:
    result = result or {}
    # Combined integrity payload from find_integrity_groups.
    if result.get("kind") == "integrity" or ("exact" in result and "near" in result):
        exact = result.get("exact") or {}
        near = result.get("near") or {}
        lines = [
            "Duplicates — integrity similarity (A)",
            "",
            "Exact = same file bytes (SHA-256).",
            "Near match = looks alike (OpenCV aHash/dHash). Not Find Similar.",
            "",
        ]
        eg = list(exact.get("groups") or [])
        ng = list(near.get("groups") or [])
        if exact.get("status") == "SUCCESS" and eg:
            lines.append(f"{len(eg)} exact group{'s' if len(eg) != 1 else ''}.")
        elif exact.get("status") == "EMPTY":
            lines.append(exact.get("reason") or "No exact duplicates.")
        elif exact.get("status") == "ERROR":
            lines.append(exact.get("reason") or "Exact scan failed.")
        near_st = str(near.get("status") or "").upper()
        if near_st == "SUCCESS" and ng:
            lines.append(f"{len(ng)} near-match group{'s' if len(ng) != 1 else ''}.")
        elif near_st == "UNAVAILABLE":
            lines.append(near.get("reason") or "Near duplicates unavailable.")
        elif near_st == "EMPTY":
            lines.append(near.get("reason") or "No near duplicates.")
        elif near_st == "ERROR":
            lines.append(near.get("reason") or "Near scan failed.")
        lines.append("")
        lines.append("Open a group to Compare · Keep / Reject are session-only.")
        shown = 0
        for g in eg[:8]:
            shown += 1
            mid_n = len(g.get("media_ids") or [])
            lines.append(
                f"Exact {shown} — {g.get('count')} files"
                + (f" ({mid_n} in library)" if mid_n else "")
            )
        for g in ng[:8]:
            shown += 1
            mid_n = len(g.get("media_ids") or [])
            lines.append(
                f"Near {shown} — {g.get('count')} files"
                + (f" ({mid_n} in library)" if mid_n else "")
            )
        return lines

    status = str(result.get("status") or "").upper()
    kind = str(result.get("kind") or EXACT_KIND)
    if status == "ERROR":
        return [result.get("reason") or "Duplicate scan failed.", "", "Your library stays open."]
    if status == "CANCELLED":
        return [result.get("reason") or "Duplicate scan cancelled."]
    if status == "UNAVAILABLE":
        return [
            result.get("reason") or "Near duplicates unavailable.",
            "",
            similarity_basis_label(kind),
        ]
    if status == "EMPTY":
        lines = [
            result.get("reason") or "No duplicate candidates were found.",
            "",
            f"Scanned {int(result.get('scanned_files') or 0)} files.",
            similarity_basis_label(kind),
        ]
        return lines

    groups = list(result.get("groups") or [])
    n = len(groups)
    label = "exact duplicate" if kind == EXACT_KIND else "near-match"
    lines = [
        f"{n} {label} group{'s' if n != 1 else ''}.",
        "",
        similarity_basis_label(kind),
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
    return lines


def open_group_lines(group: dict | None, *, index: int = 1) -> list[str]:
    group = group or {}
    members = list(group.get("members") or [])
    kind = str(group.get("kind") or EXACT_KIND)
    lines = [
        f"Duplicate group {index} — {len(members)} files",
        "",
        similarity_basis_label(kind),
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
