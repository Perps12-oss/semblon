"""Interactive Review — tkinter over existing review APIs.

Clusters are evidence. People exist only after an explicit Name action.
Does not retune clustering. Does not identify. Static review.html stays read-only.

UX presentation only (Rescue §§8–9). Identity / apply_* semantics unchanged.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from semblon.export import STRONG_MIN_INTRA
from semblon.process import default_store_path, empty_state_line, latest_run_id
from semblon.review import (
    ReviewError,
    ignore_subject,
    merge_clusters,
    name_cluster,
    name_face,
    name_faces,
    note_subject,
    rule_out_subject,
    ruled_out_enabled,
    split_cluster,
)
from semblon.tracks import TracksError, derive_tracks

THUMB_MAX = 96
_FRAME_CACHE_MAX = 64
_CROP_CACHE_MAX = 256

# Design tokens (UX Rescue §1). Soft fallback if tokens module is mid-merge.
try:
    from semblon.ui_theme import apply_theme, style_listbox
    from semblon.ui_tokens import (
        ACCENT,
        ACCENT_SUBTLE,
        BG_CANVAS,
        BG_DARK,
        BG_SUBTLE,
        BODY,
        BODY_STRONG,
        H1,
        H2,
        INK_ON_ACCENT,
        INK_ON_DARK,
        INK_PRIMARY,
        INK_SECONDARY,
        SECONDARY_FONT,
    )
    from semblon.ui_widgets import Button as RoleButton
except ImportError:  # pragma: no cover
    apply_theme = None
    style_listbox = None
    RoleButton = None
    ACCENT = "#2E6BE6"
    ACCENT_SUBTLE = "#EEF0FB"
    BG_CANVAS = "#FBFAF7"
    BG_DARK = "#14130F"
    BG_SUBTLE = "#F6F4EF"
    BODY = ("Segoe UI", 13)
    BODY_STRONG = ("Segoe UI", 13, "bold")
    H1 = ("Segoe UI", 24, "bold")
    H2 = ("Segoe UI", 18, "bold")
    INK_ON_ACCENT = "#FFFFFF"
    INK_ON_DARK = "#B5B1A8"
    INK_PRIMARY = "#1A1815"
    INK_SECONDARY = "#5E5A52"
    SECONDARY_FONT = ("Segoe UI", 13)

# Review visual chrome (presentation only — no identity / clustering changes).
GROUP_THUMB = 40
GROUP_ROW_H = 56
GROUP_REPR_FACES = 3
MERGE_THUMB = 72
MERGE_REPR_FACES = 5
FACE_GRID_WRAP = 720
FACE_BORDER_MUTED = "#6B675F"
FACE_BORDER_HOVER = "#9B96EC"
FACE_CHECK_SIZE = 22
FACE_DIM_FILL = "#000000"

_FONT_UI = BODY
_FONT_UI_BOLD = BODY_STRONG
_FONT_HEADLINE = H1
_FONT_BANNER = SECONDARY_FONT


def _review_button(master, text, command, kind="secondary"):
    if RoleButton is None or tk is None:
        return ttk.Button(master, text=text, command=command)
    return RoleButton(master, text=text, command=command, kind=kind, plate=BG_CANVAS)

REVIEW_WINDOW_TITLE = "Review faces"
REVIEW_BANNER = (
    "Semblon has grouped faces it thinks belong to the same person. "
    "You decide the name."
)
EMPTY_ENTRY_HEADLINE = "Nothing to review yet"
EMPTY_ENTRY_BODY = (
    "Add a photo folder first. Semblon will find and group faces for you to review here."
)
NAME_SUCCESS_STATUS = "Named. Semblon will remember this face."

tk = ttk = messagebox = simpledialog = filedialog = None

# Bounded LRU caches for decoded frames and PNG crops (process-local).
_frame_cache: OrderedDict[tuple, object] = OrderedDict()
_crop_cache: OrderedDict[tuple, str] = OrderedDict()
_frame_lock = threading.Lock()


def _ensure_tk() -> None:
    """Load tkinter only when the window runs. Board/API stay headless."""
    global tk, ttk, messagebox, simpledialog, filedialog
    if tk is not None:
        return
    import tkinter as _tk
    from tkinter import filedialog as _fd
    from tkinter import messagebox as _mb
    from tkinter import simpledialog as _sd
    from tkinter import ttk as _ttk

    tk = _tk
    ttk = _ttk
    messagebox = _mb
    simpledialog = _sd
    filedialog = _fd


class ReviewUiError(ValueError):
    pass


class ReviewExpectedEmpty(ReviewUiError):
    """No store or no runs yet — coaching empty state, not an Error dialog."""

    def __init__(self, reason: str):
        self.reason = reason  # "no_store" | "no_runs"
        super().__init__(reason)


def _ro_connect(store: Path) -> sqlite3.Connection:
    """Read-only store connection. Waits on the existing writer (busy_timeout=5000)."""
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def make_review_root(parent=None, *, tk_mod=None):
    """Tk when standalone; Toplevel on Home's root so Home keeps pumping events."""
    if tk_mod is None:
        _ensure_tk()
        tk_mod = tk
    if parent is not None:
        return tk_mod.Toplevel(parent), False
    return tk_mod.Tk(), True


def resolve_run_id(store: Path, run_id: str | None) -> str:
    """Use --run when given; otherwise the latest run that still has faces.

    Empty incremental runs (FACE-005 skip-all) must not hide a prior populated run.
    Expected empty (no store / no runs) raises ReviewExpectedEmpty — not a hard Error.
    """
    store = Path(store)
    if not store.is_file():
        raise ReviewExpectedEmpty("no_store")
    if run_id:
        try:
            conn = _ro_connect(store)
            row = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
            conn.close()
        except sqlite3.Error as e:
            raise ReviewUiError(f"couldn't read the library: {e}") from e
        if row is None:
            raise ReviewUiError(f"unknown run: {run_id}")
        return run_id
    try:
        rid = latest_run_id(store, with_faces=True) or latest_run_id(store)
    except sqlite3.Error as e:
        raise ReviewUiError(f"couldn't read the library: {e}") from e
    if rid is None:
        raise ReviewExpectedEmpty("no_runs")
    return rid


def _basename(path: str) -> str:
    return Path(path or "").name or (path or "")


def _decision_sets(decisions) -> tuple[set[str], set[str], set[str], set[str]]:
    """ignored_faces, ignored_clusters, noted_faces, noted_clusters."""
    ignored_faces: set[str] = set()
    ignored_clusters: set[str] = set()
    noted_faces: set[str] = set()
    noted_clusters: set[str] = set()
    for d in decisions:
        try:
            pol = json.loads(d["policy_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            pol = {}
        if not isinstance(pol, dict):
            pol = {}
        kind = d["kind"]
        fid = d["face_id"]
        cid = d["cluster_id"]
        if kind == "reject" and pol.get("action") == "ignore":
            if fid:
                ignored_faces.add(fid)
            elif cid:
                ignored_clusters.add(cid)
        if kind == "note":
            if fid:
                noted_faces.add(fid)
            if cid:
                noted_clusters.add(cid)
    return ignored_faces, ignored_clusters, noted_faces, noted_clusters


def _track_items(
    store: Path,
    run_id: str,
    video_faces: list[dict],
    *,
    cached: dict | None = None,
) -> tuple[list[dict], list[dict], dict | None]:
    """Render derived S7 tracks. Leftovers stay untracked observations."""
    if not video_faces:
        return [], [], cached
    face_key = tuple(sorted(f["face_id"] for f in video_faces))
    if cached and cached.get("face_key") == face_key:
        rec = cached["rec"]
    else:
        try:
            rec = derive_tracks(store, run_id)
        except TracksError:
            return [], list(video_faces), None
        cached = {"face_key": face_key, "rec": rec}
    by_id = {f["face_id"]: f for f in video_faces}
    used: set[str] = set()
    items: list[dict] = []
    for tr in rec["tracks"]:
        members = [by_id[fid] for fid in tr["face_ids"] if fid in by_id]
        if len(members) < 2:
            continue
        used.update(m["face_id"] for m in members)
        person_names = sorted({m["person_name"] for m in members if m["person_name"]})
        items.append(
            {
                "kind": "track",
                "track_id": tr["track_id"],
                "media_id": tr["media_id"],
                "path": tr["path"],
                "face_id": "",
                "band": "unassigned",
                "face_count": len(members),
                "min_intra": None,
                "status": "ok",
                "person_names": person_names,
                "named": bool(person_names),
                "t_ms_start": tr["t_ms_start"],
                "t_ms_end": tr["t_ms_end"],
                "representative_face_id": tr["representative_face_id"],
                "members": members,
                "has_note": False,
                "note": "temporal association; not a person",
            }
        )
    leftover = [f for f in video_faces if f["face_id"] not in used]
    return items, leftover, cached


def load_board(
    store: Path,
    run_id: str,
    *,
    strong_min_intra: float = STRONG_MIN_INTRA,
    tracks_cache: dict | None = None,
) -> dict:
    """Read-only board for the review UI. Does not enrol anyone."""
    store = Path(store)
    conn = _ro_connect(store)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ReviewUiError(f"unknown run: {run_id}")

    clusters = conn.execute(
        """SELECT * FROM clusters WHERE run_id=?
           ORDER BY min_intra ASC, face_count DESC""",
        (run_id,),
    ).fetchall()
    faces = conn.execute(
        """
        SELECT f.*, m.path, m.source_type, m.media_id,
               o.observation_id AS obs_id, o.frame_id, o.t_ms,
               p.display_name AS person_name
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        LEFT JOIN persons p ON p.person_id = f.person_id
        WHERE f.run_id=?
        ORDER BY f.face_id
        """,
        (run_id,),
    ).fetchall()
    decisions = conn.execute(
        """SELECT * FROM decisions WHERE run_id=?
           ORDER BY created_at, decision_id""",
        (run_id,),
    ).fetchall()
    persons = conn.execute(
        """SELECT person_id, display_name, status FROM persons
           WHERE status='active' ORDER BY display_name"""
    ).fetchall()

    ignored_faces, ignored_clusters, noted_faces, noted_clusters = _decision_sets(decisions)

    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for f in faces:
        if f["face_id"] in ignored_faces:
            continue
        rec = {
            "face_id": f["face_id"],
            "observation_id": f["obs_id"],
            "cluster_id": f["cluster_id"],
            "person_id": f["person_id"],
            "person_name": f["person_name"],
            "status": f["status"],
            "source_type": f["source_type"],
            "media_id": f["media_id"],
            "path": f["path"],
            "frame_id": f["frame_id"],
            "t_ms": f["t_ms"],
            "bbox": (f["bbox_x1"], f["bbox_y1"], f["bbox_x2"], f["bbox_y2"]),
            "face_w": f["face_w"],
            "face_h": f["face_h"],
            "has_note": f["face_id"] in noted_faces,
        }
        if f["cluster_id"]:
            by_cluster.setdefault(f["cluster_id"], []).append(rec)
        elif f["status"] == "ok":
            unassigned.append(rec)

    items: list[dict] = []
    for c in clusters:
        if c["status"] == "ignored" or c["cluster_id"] in ignored_clusters:
            continue
        members = by_cluster.get(c["cluster_id"], [])
        mi = c["min_intra"]
        band = "review" if (mi is None or mi < strong_min_intra) else "strong"
        person_names = sorted(
            {m["person_name"] for m in members if m["person_name"]}
        )
        items.append(
            {
                "kind": "cluster",
                "cluster_id": c["cluster_id"],
                "band": band,
                "face_count": c["face_count"],
                "min_intra": mi,
                "status": c["status"],
                "person_names": person_names,
                "named": bool(person_names),
                "members": members,
                "has_note": c["cluster_id"] in noted_clusters,
            }
        )

    items.sort(
        key=lambda it: (
            0 if it["band"] == "review" else 1,
            it["min_intra"] is None,
            it["min_intra"] if it["min_intra"] is not None else 0.0,
            -it["face_count"],
        )
    )

    still_unassigned: list[dict] = []
    video_unassigned: list[dict] = []
    for u in unassigned:
        if u["source_type"] == "video":
            video_unassigned.append(u)
        else:
            still_unassigned.append(u)

    track_items, leftover_video, tracks_cache = _track_items(
        store, run_id, video_unassigned, cached=tracks_cache
    )
    items.extend(track_items)
    for u in leftover_video + still_unassigned:
        items.append(
            {
                "kind": "unassigned",
                "face_id": u["face_id"],
                "band": "unassigned",
                "face_count": 1,
                "min_intra": None,
                "status": u["status"],
                "person_names": [u["person_name"]] if u["person_name"] else [],
                "named": bool(u["person_name"]),
                "members": [u],
                "has_note": bool(u.get("has_note")),
            }
        )

    board = {
        "store": str(store.resolve()),
        "run_id": run_id,
        "pack_id": run["pack_id"],
        "strong_min_intra": strong_min_intra,
        "items": items,
        "decisions": [
            {
                "kind": d["kind"],
                "cluster_id": d["cluster_id"],
                "face_id": d["face_id"],
                "person_id": d["person_id"],
                "created_at": d["created_at"],
            }
            for d in decisions
        ],
        "persons": [
            {
                "person_id": p["person_id"],
                "display_name": p["display_name"],
            }
            for p in persons
        ],
        "counts": {
            "clusters": sum(1 for c in clusters if c["status"] != "ignored"),
            "review_required": sum(1 for it in items if it["band"] == "review"),
            "strong": sum(1 for it in items if it["band"] == "strong"),
            "unassigned": len(unassigned),
            "tracks": sum(1 for it in items if it["kind"] == "track"),
            "untracked": sum(
                1
                for it in items
                if it["kind"] == "unassigned"
                and it["members"]
                and it["members"][0].get("source_type") == "video"
            ),
            "named_persons": len(persons),
            "decisions": len(decisions),
            "faces": len(faces),
            "ok": sum(1 for f in faces if f["status"] == "ok"),
            "ignored_faces": len(ignored_faces),
            "ignored_clusters": len(ignored_clusters),
        },
        "empty_state": empty_state_line(store, run_id),
        "_tracks_cache": tracks_cache,
    }
    conn.close()
    return board


def _lru_set(cache: OrderedDict, key, value, max_size: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_size:
        cache.popitem(last=False)


def _read_frame_bgr(path: str, frame_id: int | None, source_type: str | None):
    from semblon.temporal import read_bgr

    key = (str(path), None if frame_id is None else int(frame_id), source_type or "")
    with _frame_lock:
        if key in _frame_cache:
            _frame_cache.move_to_end(key)
            return _frame_cache[key]
    if source_type == "video":
        if frame_id is None:
            return None
        img = read_bgr(path, int(frame_id))
    else:
        img = read_bgr(path, None)
    if img is not None:
        with _frame_lock:
            _lru_set(_frame_cache, key, img, _FRAME_CACHE_MAX)
    return img


def _crop_bgr(
    path: str,
    bbox,
    max_side: int = THUMB_MAX,
    *,
    frame_id: int | None = None,
    source_type: str | None = None,
):
    """Decode once (cached) and return a BGR crop, or None."""
    try:
        import cv2
    except ImportError:
        return None
    img = _read_frame_bgr(path, frame_id, source_type)
    if img is None:
        return None
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    ch, cw = crop.shape[:2]
    m = max(ch, cw)
    if m > max_side:
        scale = max_side / float(m)
        crop = cv2.resize(
            crop,
            (max(1, int(cw * scale)), max(1, int(ch * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return crop


def crop_png_b64(
    path: str,
    bbox,
    max_side: int = THUMB_MAX,
    *,
    frame_id: int | None = None,
    source_type: str | None = None,
) -> str | None:
    """Face crop as base64 PNG for tk.PhotoImage (no PIL required)."""
    try:
        import base64

        import cv2
    except ImportError:
        return None
    bb = tuple(float(v) for v in bbox)
    key = (str(path), None if frame_id is None else int(frame_id), bb, int(max_side), "png")
    with _frame_lock:
        if key in _crop_cache:
            _crop_cache.move_to_end(key)
            return _crop_cache[key]
    crop = _crop_bgr(
        path, bbox, max_side=max_side, frame_id=frame_id, source_type=source_type
    )
    if crop is None:
        return None
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return None
    out = base64.b64encode(buf.tobytes()).decode("ascii")
    with _frame_lock:
        _lru_set(_crop_cache, key, out, _CROP_CACHE_MAX)
    return out


def crop_jpeg_bytes(
    path: str,
    bbox,
    max_side: int = THUMB_MAX,
    *,
    frame_id: int | None = None,
    source_type: str | None = None,
) -> bytes | None:
    """JPEG bytes for tests / non-tk consumers."""
    try:
        import cv2
    except ImportError:
        return None
    crop = _crop_bgr(
        path, bbox, max_side=max_side, frame_id=frame_id, source_type=source_type
    )
    if crop is None:
        return None
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return None
    return buf.tobytes()


def apply_name(store: Path, run_id: str, item: dict, display_name: str) -> dict:
    if item["kind"] == "cluster":
        return name_cluster(store, run_id, item["cluster_id"], display_name)
    if item["kind"] == "track":
        members = [m["face_id"] for m in item.get("members") or []]
        rec = name_faces(
            store,
            run_id,
            members,
            display_name,
            source="track",
            track_id=item.get("track_id"),
        )
        if rec.get("track_id") and rec.get("person_id") and rec["track_id"] == rec["person_id"]:
            raise ReviewUiError("track id must not equal person id")
        return rec
    fid = item.get("face_id")
    if not fid:
        raise ReviewUiError("select an unassigned face to Name")
    return name_face(store, run_id, fid, display_name)


def apply_merge(store: Path, run_id: str, cluster_ids: list[str]) -> dict:
    return merge_clusters(store, run_id, cluster_ids)


def apply_split(store: Path, run_id: str, cluster_id: str, face_ids: list[str]) -> dict:
    return split_cluster(store, run_id, cluster_id, face_ids)


def apply_ignore(store: Path, run_id: str, item: dict, disposition: str | None = None) -> dict:
    if item["kind"] == "cluster":
        return ignore_subject(
            store, run_id, cluster_id=item["cluster_id"], disposition=disposition or "not_a_person"
        )
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Ignore (a track is not a person)")
    # Pass disposition through; backend defaults face ignore to needs-review.
    return ignore_subject(store, run_id, face_id=fid, disposition=disposition)


def apply_rule_out(
    store: Path,
    run_id: str,
    item: dict,
    *,
    person_id: str | None = None,
    text: str | None = None,
) -> dict:
    """Durable Ruled out. Gated by SEMBLON_RULED_OUT (default ON; opt out =0)."""
    if item["kind"] == "cluster":
        return rule_out_subject(
            store,
            run_id,
            cluster_id=item["cluster_id"],
            person_id=person_id,
            text=text,
        )
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Rule out (a track is not a person)")
    if not fid:
        raise ReviewUiError("select a cluster or face to Rule out")
    return rule_out_subject(
        store, run_id, face_id=fid, person_id=person_id, text=text
    )


def apply_note(store: Path, run_id: str, item: dict, text: str) -> dict:
    if item["kind"] == "cluster":
        return note_subject(store, run_id, cluster_id=item["cluster_id"], text=text)
    fid = item.get("face_id")
    if item["kind"] == "track" and not fid:
        raise ReviewUiError("click a face in the video to Note (a track is not a person)")
    return note_subject(store, run_id, face_id=fid, text=text)


def _photo_count_phrase(n: int) -> str:
    return f"{n} photo" if n == 1 else f"{n} photos"


def item_label(item: dict, *, detail: bool = False) -> str:
    """List label for a board item. Soft by default; detail keeps STRONG/ids/min_intra."""
    note_tag = " [note]" if item.get("has_note") else ""
    if detail:
        return _item_label_detail(item, note_tag=note_tag)
    return _item_label_soft(item, note_tag=note_tag)


def _item_label_soft(item: dict, *, note_tag: str = "") -> str:
    if item["kind"] == "track":
        name = _basename(item.get("path") or "") or "video"
        named = (
            f" — {', '.join(item['person_names'])}"
            if item["named"]
            else ""
        )
        return (
            f"Video group · {name} · {_photo_count_phrase(item['face_count'])}"
            f"{named}{note_tag}"
        )
    if item["kind"] == "unassigned":
        if item["named"]:
            return f"Single face — {item['person_names'][0]}{note_tag}"
        return f"Single face · needs a name{note_tag}"
    # cluster — hide band / id / min_intra in normal view
    photos = _photo_count_phrase(item["face_count"])
    if item["named"]:
        return f"{', '.join(item['person_names'])} · {photos}{note_tag}"
    return f"Likely the same person · {photos}{note_tag}"


def _item_label_detail(item: dict, *, note_tag: str = "") -> str:
    if item["kind"] == "track":
        name = _basename(item.get("path") or "")
        tag = f" named:{','.join(item['person_names'])}" if item["named"] else " unnamed"
        t0 = item.get("t_ms_start")
        t1 = item.get("t_ms_end")
        return f"TRACK {name}  n={item['face_count']}  t={t0}-{t1}ms{tag}{note_tag}"
    if item["kind"] == "unassigned":
        fid = item["face_id"][:8]
        tag = f" named:{item['person_names'][0]}" if item["named"] else " unnamed"
        return f"UNASSIGNED {fid}{tag}{note_tag}"
    cid = item["cluster_id"][:8]
    band = item["band"].upper()
    named = (
        f" person={','.join(item['person_names'])}"
        if item["named"]
        else " unnamed"
    )
    mi = "—" if item["min_intra"] is None else f"{item['min_intra']:.3f}"
    return f"{band} {cid}  n={item['face_count']}  min_intra={mi}{named}{note_tag}"


def review_status_text(board: dict, *, detail: bool = False) -> str:
    """Primary status for the Review banner area."""
    clusters = [it for it in board.get("items") or [] if it["kind"] == "cluster"]
    n = len(clusters)
    named = sum(1 for it in clusters if it.get("named"))
    if detail:
        c = board.get("counts") or {}
        run_id = board.get("run_id") or ""
        store = board.get("store") or ""
        return (
            f"store={store}  run={run_id}  "
            f"review={c.get('review_required', 0)} strong={c.get('strong', 0)} "
            f"unassigned={c.get('unassigned', 0)} tracks={c.get('tracks', 0)} "
            f"untracked={c.get('untracked', 0)} "
            f"persons={c.get('named_persons', 0)} "
            f"decisions={c.get('decisions', 0)}"
        )
    if n == 0:
        return "No groups to review yet."
    if named == 0:
        return f"{n} groups to review. None named yet."
    return f"{named} of {n} groups named."


def visible_review_items(
    items: list[dict] | None, *, show_singles: bool = False
) -> list[dict]:
    """Filter board items for the Groups list. Singles hidden by default."""
    rows = list(items or [])
    if show_singles:
        return rows
    return [it for it in rows if it.get("kind") != "unassigned"]


def representative_members(item: dict | None, limit: int = GROUP_REPR_FACES) -> list[dict]:
    """First N face members for list / merge thumbnails."""
    if not item:
        return []
    members = item.get("members") or []
    n = max(0, int(limit))
    return list(members[:n])


def cluster_items_at_indices(items: list[dict], indices: list[int] | set[int]) -> list[dict]:
    """Cluster rows at the given list indices (order preserved, de-duped)."""
    out: list[dict] = []
    seen: set[str] = set()
    for i in sorted(indices):
        if i < 0 or i >= len(items):
            continue
        it = items[i]
        if it.get("kind") != "cluster":
            continue
        cid = it.get("cluster_id")
        if not cid or cid in seen:
            continue
        seen.add(str(cid))
        out.append(it)
    return out


def split_button_label(n_selected: int) -> str:
    """Live Split button copy. Zero stays generic (button may be disabled)."""
    n = max(0, int(n_selected))
    if n <= 0:
        return "Split selected"
    if n == 1:
        return "Split 1 selected"
    return f"Split {n} selected"


def face_border_style(*, selected: bool, hovered: bool = False) -> tuple[str, int]:
    """(outline_color, width) for a face crop frame."""
    if selected:
        return (ACCENT, 3)
    if hovered:
        return (FACE_BORDER_HOVER, 2)
    return (FACE_BORDER_MUTED, 1)


def _actions_for_kind(kind: str) -> dict[str, bool]:
    """Which review buttons apply to the selected item kind."""
    rule_out = ruled_out_enabled()
    if kind == "cluster":
        return {
            "name": True,
            "merge": True,
            "split": True,
            "ignore": True,
            "note": True,
            "rule_out": rule_out,
        }
    if kind == "track":
        return {
            "name": True,
            "merge": False,
            "split": False,
            "ignore": False,
            "note": False,
            "rule_out": False,
        }
    if kind == "unassigned":
        return {
            "name": True,
            "merge": False,
            "split": False,
            "ignore": True,
            "note": True,
            "rule_out": rule_out,
        }
    return {
        "name": False,
        "merge": False,
        "split": False,
        "ignore": False,
        "note": False,
        "rule_out": False,
    }


class ReviewApp:
    """Minimal tkinter surface. All mutations go through review.py."""

    def __init__(
        self,
        store: Path,
        run_id: str | None,
        *,
        parent=None,
        empty_reason: str | None = None,
        on_add_folder: Callable[[], None] | None = None,
    ):
        _ensure_tk()
        self.store = Path(store)
        self.run_id = run_id
        self.empty_reason = empty_reason
        self.on_add_folder = on_add_folder
        self._tracks_cache: dict | None = None
        self._photos: list = []
        self._group_photos: list = []
        self._merge_photos: list = []
        self._selected_faces: set[str] = set()
        self._draw_gen = 0
        self._group_draw_gen = 0
        self._detail_mode = False
        self._show_singles = False
        self._visible_items: list[dict] = []
        self._sel_indices: set[int] = set()
        self._primary_index: int | None = None
        self._hover_face_id: str | None = None
        self._face_slots: dict[str, dict] = {}
        self.board: dict = {
            "items": [],
            "counts": {},
            "empty_state": "",
            "store": str(self.store),
            "run_id": run_id or "",
        }

        self.root, self._owns_loop = make_review_root(parent)
        self.root.title(REVIEW_WINDOW_TITLE)
        self.root.geometry("980x640")
        self.root.minsize(880, 640)
        if apply_theme is not None:
            apply_theme(self.root)

        if empty_reason is not None or run_id is None:
            self._build_entry_empty()
            return

        self.board = load_board(self.store, self.run_id)
        self._tracks_cache = self.board.get("_tracks_cache")
        self._build_review_chrome()
        self.reload()

    def _build_entry_empty(self) -> None:
        """§8 — coaching empty state when there is no store / no runs."""
        frame = ttk.Frame(self.root, padding=28)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame, text=EMPTY_ENTRY_HEADLINE, font=_FONT_HEADLINE
        ).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text=EMPTY_ENTRY_BODY,
            font=_FONT_UI,
            wraplength=560,
        ).pack(anchor=tk.W, pady=(10, 20))
        row = ttk.Frame(frame)
        row.pack(anchor=tk.W)
        _review_button(row, "Add a photo folder", self._do_add_folder, kind="primary").pack(
            side=tk.LEFT, padx=(0, 8)
        )
        _review_button(row, "Close", self.root.destroy, kind="tertiary").pack(side=tk.LEFT)

    def _do_add_folder(self) -> None:
        cb = self.on_add_folder
        if cb is None:
            master = getattr(self.root, "master", None)
            attached = getattr(master, "semblon_add_folder", None) if master else None
            if callable(attached):
                cb = attached
        if cb is not None:
            self.root.destroy()
            cb()
            return
        folder = filedialog.askdirectory(
            title="Choose a folder of photos for Semblon", parent=self.root
        )
        if folder:
            messagebox.showinfo(
                REVIEW_WINDOW_TITLE,
                (
                    f"Folder selected:\n{folder}\n\n"
                    "Open Semblon Home and add this folder to process photos, "
                    "then reopen Review."
                ),
                parent=self.root,
            )
        else:
            messagebox.showinfo(
                REVIEW_WINDOW_TITLE,
                "Add a photo folder from Semblon Home, then open Review again.",
                parent=self.root,
            )
        self.root.destroy()

    def _build_review_chrome(self) -> None:
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text=REVIEW_BANNER, font=_FONT_BANNER, wraplength=900).pack(
            anchor=tk.W
        )
        run_line = ttk.Frame(top)
        run_line.pack(anchor=tk.W, fill=tk.X, pady=(4, 0))
        self._run_id_var = tk.StringVar(value="")
        self._run_id_label = ttk.Label(
            run_line, textvariable=self._run_id_var, font=_FONT_UI, foreground=INK_SECONDARY
        )
        # Packed only when Details is on — hide developer run id by default.
        self._detail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run_line,
            text="Details",
            variable=self._detail_var,
            command=self._toggle_details,
        ).pack(side=tk.RIGHT)
        self._singles_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run_line,
            text="Show single faces",
            variable=self._singles_var,
            command=self._toggle_singles,
        ).pack(side=tk.RIGHT, padx=(0, 12))
        self.empty_state = ttk.Label(top, text="", font=_FONT_UI)
        self.empty_state.pack(anchor=tk.W)
        self.status = ttk.Label(top, text="", font=_FONT_UI_BOLD)
        self.status.pack(anchor=tk.W)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=3)

        ttk.Label(left, text="Groups", font=_FONT_UI).pack(anchor=tk.W)
        ttk.Label(
            left,
            text="Ctrl+click to select several groups, then Merge selected.",
            font=_FONT_BANNER,
            foreground=INK_SECONDARY,
            wraplength=280,
        ).pack(anchor=tk.W, pady=(0, 4))
        group_wrap = ttk.Frame(left)
        group_wrap.pack(fill=tk.BOTH, expand=True)
        self.group_canvas = tk.Canvas(
            group_wrap,
            background=BG_SUBTLE,
            highlightthickness=0,
            width=300,
        )
        group_sb = ttk.Scrollbar(
            group_wrap, orient=tk.VERTICAL, command=self.group_canvas.yview
        )
        self.group_canvas.configure(yscrollcommand=group_sb.set)
        self.group_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        group_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_canvas.bind("<Button-1>", self._on_group_click)
        self.group_canvas.bind(
            "<Control-Button-1>", lambda e: self._on_group_click(e, additive=True)
        )
        self.group_canvas.bind(
            "<MouseWheel>",
            lambda e: self.group_canvas.yview_scroll(int(-e.delta / 120), "units"),
        )
        # Compat alias: older helpers may still look for listbox.
        self.listbox = self.group_canvas

        ttk.Label(
            right, text="Faces (click to mark for Split · scroll for all)", font=_FONT_UI
        ).pack(anchor=tk.W)
        face_wrap = ttk.Frame(right)
        face_wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(
            face_wrap, background=BG_DARK, height=420, highlightthickness=0
        )
        face_sb = ttk.Scrollbar(face_wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=face_sb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        face_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_face_motion)
        self.canvas.bind("<Leave>", self._on_face_leave)
        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"),
        )
        self._hover_face_id: str | None = None
        self._face_slots: dict[str, dict] = {}

        actions = ttk.Frame(self.root, padding=6)
        actions.pack(fill=tk.X)
        self.btn_name = _review_button(actions, "Name", self._do_name, kind="primary")
        self.btn_name.pack(side=tk.LEFT, padx=2)
        self.btn_merge = _review_button(
            actions, "Merge groups…", self._do_merge, kind="secondary"
        )
        self.btn_merge.pack(side=tk.LEFT, padx=2)
        self.btn_split = _review_button(
            actions, "Split selected", self._do_split, kind="secondary"
        )
        self.btn_split.pack(side=tk.LEFT, padx=2)
        self.btn_ignore = _review_button(actions, "Ignore", self._do_ignore, kind="secondary")
        self.btn_ignore.pack(side=tk.LEFT, padx=2)
        self.btn_note = _review_button(actions, "Note…", self._do_note, kind="secondary")
        self.btn_note.pack(side=tk.LEFT, padx=2)
        self.btn_rule_out = _review_button(
            actions, "Rule out…", self._do_rule_out, kind="destructive"
        )
        self.btn_rule_out.pack(side=tk.LEFT, padx=2)
        _review_button(actions, "Refresh view", self.reload, kind="tertiary").pack(
            side=tk.LEFT, padx=2
        )
        _review_button(actions, "Close", self.root.destroy, kind="tertiary").pack(
            side=tk.RIGHT, padx=2
        )
        self._btn_map = {
            "name": self.btn_name,
            "merge": self.btn_merge,
            "split": self.btn_split,
            "ignore": self.btn_ignore,
            "note": self.btn_note,
            "rule_out": self.btn_rule_out,
        }
        self.root.bind("<Return>", lambda _e: self._do_name())
        self.root.bind("<Delete>", lambda _e: self._do_ignore())
        self.root.bind("n", lambda _e: self._do_note())
        self.root.bind("N", lambda _e: self._do_note())
        self.root.bind("m", lambda _e: self._do_merge())
        self.root.bind("M", lambda _e: self._do_merge())
        self.root.bind("s", lambda _e: self._do_split())
        self.root.bind("S", lambda _e: self._do_split())
        self.root.bind("i", lambda _e: self._do_ignore())
        self.root.bind("I", lambda _e: self._do_ignore())
        self._sync_run_id_visibility()

    def _toggle_details(self) -> None:
        self._detail_mode = bool(self._detail_var.get())
        self._sync_run_id_visibility()
        self._refresh_list_and_status()

    def _sync_run_id_visibility(self) -> None:
        """Show Run id only when Details is on (developer chrome demotion)."""
        if not hasattr(self, "_run_id_label"):
            return
        if self._detail_mode and self.run_id:
            self._run_id_var.set(f"Run {self.run_id}")
            if not self._run_id_label.winfo_ismapped():
                self._run_id_label.pack(side=tk.LEFT)
        else:
            self._run_id_var.set("")
            self._run_id_label.pack_forget()

    def _toggle_singles(self) -> None:
        self._show_singles = bool(self._singles_var.get())
        self._refresh_list_and_status()

    def _refresh_list_and_status(self) -> None:
        prev_keys = []
        for i in sorted(self._sel_indices):
            if 0 <= i < len(self._visible_items):
                prev_keys.append(self._item_key(self._visible_items[i]))
        primary_key = None
        if self._primary_index is not None and 0 <= self._primary_index < len(
            self._visible_items
        ):
            primary_key = self._item_key(self._visible_items[self._primary_index])

        self._visible_items = visible_review_items(
            self.board.get("items") or [], show_singles=self._show_singles
        )
        self._sel_indices = set()
        self._primary_index = None
        for i, it in enumerate(self._visible_items):
            key = self._item_key(it)
            if key in prev_keys:
                self._sel_indices.add(i)
            if primary_key is not None and key == primary_key:
                self._primary_index = i
        if self._primary_index is None and self._sel_indices:
            self._primary_index = min(self._sel_indices)

        self._redraw_group_list()
        detail_bits = []
        if self._detail_mode and self.board.get("empty_state"):
            detail_bits.append(self.board["empty_state"])
        hidden = sum(
            1
            for it in (self.board.get("items") or [])
            if it.get("kind") == "unassigned"
        )
        if not self._show_singles and hidden:
            detail_bits.append(
                f"{hidden} single face{'s' if hidden != 1 else ''} hidden — "
                "enable Show single faces to review them."
            )
        self.empty_state.config(text="  ".join(detail_bits))
        self.status.config(
            text=review_status_text(self.board, detail=self._detail_mode)
        )
        self._update_action_buttons()

    @staticmethod
    def _item_key(item: dict) -> str:
        kind = item.get("kind") or ""
        if kind == "cluster":
            return f"cluster:{item.get('cluster_id')}"
        if kind == "track":
            return f"track:{item.get('track_id')}"
        return f"face:{item.get('face_id')}"

    def _redraw_group_list(self) -> None:
        self._group_draw_gen += 1
        gen = self._group_draw_gen
        self.group_canvas.delete("all")
        self._group_photos = []
        y = 4
        slots: list[tuple] = []
        for i, item in enumerate(self._visible_items):
            selected = i in self._sel_indices
            primary = i == self._primary_index
            fill = ACCENT_SUBTLE if selected else BG_CANVAS
            outline = ACCENT if primary else ("#C9C4B8" if selected else "#DDD8CE")
            tag = f"group:{i}"
            self.group_canvas.create_rectangle(
                4,
                y,
                292,
                y + GROUP_ROW_H - 4,
                fill=fill,
                outline=outline,
                width=2 if primary else 1,
                tags=(tag,),
            )
            label = item_label(item, detail=self._detail_mode)
            text_x = 12 + GROUP_REPR_FACES * (GROUP_THUMB + 4)
            if item.get("named"):
                # Named progress cue — accent check notch on the row.
                cx = 292 - 18
                cy = y + 12
                self.group_canvas.create_oval(
                    cx,
                    cy,
                    cx + 14,
                    cy + 14,
                    fill=ACCENT,
                    outline=ACCENT,
                    tags=(tag,),
                )
                self.group_canvas.create_text(
                    cx + 7,
                    cy + 7,
                    text="✓",
                    fill=INK_ON_ACCENT,
                    font=("Segoe UI", 9, "bold"),
                    tags=(tag,),
                )
            self.group_canvas.create_text(
                text_x,
                y + 10,
                anchor=tk.NW,
                fill=INK_PRIMARY,
                font=_FONT_UI,
                text=label,
                width=150 if item.get("named") else 160,
                tags=(tag,),
            )
            reps = representative_members(item, GROUP_REPR_FACES)
            for j, m in enumerate(reps):
                sx = 10 + j * (GROUP_THUMB + 4)
                sy = y + 8
                rect = self.group_canvas.create_rectangle(
                    sx,
                    sy,
                    sx + GROUP_THUMB,
                    sy + GROUP_THUMB,
                    fill="#D8D3C8",
                    outline="#B8B3A8",
                    tags=(tag,),
                )
                slots.append((gen, m, sx, sy, rect, tag))
            if not reps:
                self.group_canvas.create_text(
                    14,
                    y + 18,
                    anchor=tk.NW,
                    fill=INK_SECONDARY,
                    text="—",
                    tags=(tag,),
                )
            y += GROUP_ROW_H
        self.group_canvas.configure(scrollregion=(0, 0, 300, max(y + 8, 100)))

        if not slots:
            return

        def worker() -> None:
            results = []
            for g, m, sx, sy, rect, tag in slots:
                b64 = crop_png_b64(
                    m["path"],
                    m["bbox"],
                    max_side=GROUP_THUMB,
                    frame_id=m.get("frame_id"),
                    source_type=m.get("source_type"),
                )
                results.append((g, sx, sy, rect, tag, b64))
            self.root.after(0, lambda: self._apply_group_crops(results))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_group_crops(self, results) -> None:
        for gen, x, y, rect, tag, b64 in results:
            if gen != self._group_draw_gen:
                continue
            if b64 is None:
                continue
            try:
                photo = tk.PhotoImage(data=b64)
            except tk.TclError:
                continue
            self._group_photos.append(photo)
            self.group_canvas.delete(rect)
            self.group_canvas.create_image(x, y, anchor=tk.NW, image=photo, tags=(tag,))

    def _on_group_click(self, event, *, additive: bool = False) -> None:
        items = self.group_canvas.find_overlapping(
            event.x - 1, event.y - 1, event.x + 1, event.y + 1
        )
        idx = None
        for it in items:
            for tag in self.group_canvas.gettags(it):
                if tag.startswith("group:"):
                    try:
                        idx = int(tag.split(":", 1)[1])
                    except ValueError:
                        idx = None
                    break
            if idx is not None:
                break
        if idx is None:
            return
        if additive:
            if idx in self._sel_indices:
                self._sel_indices.discard(idx)
                if self._primary_index == idx:
                    self._primary_index = (
                        min(self._sel_indices) if self._sel_indices else None
                    )
            else:
                self._sel_indices.add(idx)
                self._primary_index = idx
        else:
            self._sel_indices = {idx}
            self._primary_index = idx
        self._redraw_group_list()
        self._selected_faces.clear()
        self._update_action_buttons()
        item = self._current_item()
        if item is None:
            self._set_empty_canvas("Select a group, track, or single face.")
            return
        self._draw_faces(item["members"])

    def reload(self, *, invalidate_tracks: bool = True) -> None:
        if self.empty_reason is not None or self.run_id is None:
            return
        if invalidate_tracks:
            self._tracks_cache = None
        self.board = load_board(
            self.store, self.run_id, tracks_cache=self._tracks_cache
        )
        self._tracks_cache = self.board.get("_tracks_cache")
        self._selected_faces.clear()
        self._refresh_list_and_status()
        item = self._current_item()
        if item is None:
            self._set_empty_canvas(
                "Nothing to review on this run. Add a photo folder, then open Review again."
                if not self._visible_items
                else "Select a group, track, or single face."
            )
        else:
            self._draw_faces(item["members"])

    def _set_empty_canvas(self, text: str) -> None:
        self.canvas.delete("all")
        self._photos = []
        self._face_slots = {}
        self._hover_face_id = None
        self.canvas.create_text(
            24, 24, anchor=tk.NW, fill=INK_ON_DARK, text=text, font=_FONT_UI
        )
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 100, 100))

    def _update_action_buttons(self) -> None:
        item = self._current_item()
        clusters = cluster_items_at_indices(self._visible_items, self._sel_indices)
        n_faces = len(self._selected_faces)
        if item is None:
            flags = _actions_for_kind("")
            if len(clusters) >= 2 or self.board["items"]:
                flags = {
                    "name": False,
                    "merge": True,
                    "split": False,
                    "ignore": False,
                    "note": False,
                    "rule_out": False,
                }
        else:
            flags = _actions_for_kind(item["kind"])
            if len(clusters) >= 2:
                flags["merge"] = True
            # Split only meaningful when faces are marked.
            if flags.get("split") and n_faces <= 0:
                flags["split"] = False
        for key, btn in self._btn_map.items():
            btn.configure(state=tk.NORMAL if flags.get(key) else tk.DISABLED)
        if len(clusters) >= 2:
            self.btn_merge.configure(text=f"Merge selected ({len(clusters)})")
        else:
            self.btn_merge.configure(text="Merge groups…")
        self.btn_split.configure(text=split_button_label(n_faces))

    def _current_item(self) -> dict | None:
        if self._primary_index is None:
            return None
        if self._primary_index < 0 or self._primary_index >= len(self._visible_items):
            return None
        return self._visible_items[self._primary_index]

    def _on_select(self, _event=None) -> None:
        """Compat no-op — group selection is handled by _on_group_click."""
        return

    def _draw_faces(self, members: list[dict]) -> None:
        self._draw_gen += 1
        gen = self._draw_gen
        self.canvas.delete("all")
        self._photos = []
        self._face_slots = {}
        self._hover_face_id = None
        if not members:
            self._set_empty_canvas("Select a group, track, or single face.")
            return
        x, y = 8, 8
        row_h = THUMB_MAX + 28
        slots = []
        for n, m in enumerate(members, start=1):
            tw = th = THUMB_MAX
            fid = m["face_id"]
            tag = f"face:{fid}"
            selected = fid in self._selected_faces
            ph = self.canvas.create_rectangle(
                x, y, x + tw, y + th, fill="#444", outline="", tags=(tag, "face_ph")
            )
            if self._detail_mode:
                label = f"{fid[:8]}"
                if m.get("source_type") == "video":
                    label += f" f={m.get('frame_id')}"
            else:
                label = f"Face {n}"
            self.canvas.create_text(
                x, y + th + 2, anchor=tk.NW, fill="#eee", text=label, tags=(tag,)
            )
            self._face_slots[fid] = {
                "x": x,
                "y": y,
                "tw": tw,
                "th": th,
                "tag": tag,
                "selected": selected,
                "ph": ph,
                "border": None,
                "dim": None,
                "check_bg": None,
                "check_txt": None,
            }
            self._paint_face_chrome(fid)
            slots.append((m, x, y, ph, tag))
            x += tw + 12
            if x > FACE_GRID_WRAP:
                x = 8
                y += row_h
        bottom = y + row_h + 8
        self.canvas.configure(scrollregion=(0, 0, FACE_GRID_WRAP + 40, bottom))
        self._update_action_buttons()

        def worker():
            results = []
            for m, sx, sy, rect, tag in slots:
                b64 = crop_png_b64(
                    m["path"],
                    m["bbox"],
                    frame_id=m.get("frame_id"),
                    source_type=m.get("source_type"),
                )
                results.append((m, sx, sy, rect, tag, b64))
            self.root.after(0, lambda: self._apply_crops(gen, results))

        threading.Thread(target=worker, daemon=True).start()

    def _paint_face_chrome(self, face_id: str, *, hovered: bool | None = None) -> None:
        """Accent border + corner check on the image; dim unselected faces."""
        slot = self._face_slots.get(face_id)
        if slot is None:
            return
        x, y, tw, th = slot["x"], slot["y"], slot["tw"], slot["th"]
        tag = slot["tag"]
        selected = face_id in self._selected_faces
        slot["selected"] = selected
        is_hover = (
            hovered
            if hovered is not None
            else (face_id == getattr(self, "_hover_face_id", None))
        )
        outline, width = face_border_style(selected=selected, hovered=bool(is_hover))

        for key in ("border", "dim", "check_bg", "check_txt"):
            item_id = slot.get(key)
            if item_id is not None:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass
                slot[key] = None

        if not selected:
            # Soften unselected so selected faces pop.
            slot["dim"] = self.canvas.create_rectangle(
                x,
                y,
                x + tw,
                y + th,
                fill=FACE_DIM_FILL,
                stipple="gray50",
                outline="",
                tags=(tag, "face_dim"),
            )

        slot["border"] = self.canvas.create_rectangle(
            x,
            y,
            x + tw,
            y + th,
            fill="",
            outline=outline,
            width=width,
            tags=(tag, "face_border"),
        )

        if selected:
            cs = FACE_CHECK_SIZE
            slot["check_bg"] = self.canvas.create_rectangle(
                x + 4,
                y + 4,
                x + 4 + cs,
                y + 4 + cs,
                fill=ACCENT,
                outline=ACCENT,
                tags=(tag, "face_check"),
            )
            slot["check_txt"] = self.canvas.create_text(
                x + 4 + cs / 2,
                y + 4 + cs / 2,
                text="✓",
                fill=INK_ON_ACCENT,
                font=("Segoe UI", 11, "bold"),
                tags=(tag, "face_check"),
            )

    def _apply_crops(self, gen: int, results) -> None:
        if gen != self._draw_gen:
            return
        for m, x, y, rect, tag, b64 in results:
            fid = m["face_id"]
            slot = self._face_slots.get(fid)
            if b64 is None:
                self.canvas.create_text(
                    x + THUMB_MAX / 2,
                    y + THUMB_MAX / 2,
                    text="file missing",
                    fill="#ccc",
                    tags=(tag,),
                )
                if slot is not None:
                    self._paint_face_chrome(fid)
                continue
            try:
                photo = tk.PhotoImage(data=b64)
            except tk.TclError:
                continue
            self._photos.append(photo)
            # Remove placeholder only — keep selection chrome above the image.
            try:
                self.canvas.delete(rect)
            except tk.TclError:
                pass
            if slot is not None and slot.get("ph") == rect:
                slot["ph"] = None
            img = self.canvas.create_image(x, y, anchor=tk.NW, image=photo, tags=(tag,))
            # Image under dim/border/check.
            try:
                self.canvas.tag_lower(img)
            except tk.TclError:
                pass
            if slot is not None:
                self._paint_face_chrome(fid)

    def _face_id_at(self, event_x: int, event_y: int) -> str | None:
        items = self.canvas.find_overlapping(
            event_x - 1, event_y - 1, event_x + 1, event_y + 1
        )
        for it in items:
            for tag in self.canvas.gettags(it):
                if tag.startswith("face:"):
                    return tag.split(":", 1)[1]
        return None

    def _on_face_motion(self, event) -> None:
        fid = self._face_id_at(event.x, event.y)
        prev = getattr(self, "_hover_face_id", None)
        if fid == prev:
            return
        self._hover_face_id = fid
        if prev and prev in self._face_slots:
            self._paint_face_chrome(prev, hovered=False)
        if fid and fid in self._face_slots:
            self._paint_face_chrome(fid, hovered=True)

    def _on_face_leave(self, _event=None) -> None:
        prev = getattr(self, "_hover_face_id", None)
        self._hover_face_id = None
        if prev and prev in self._face_slots:
            self._paint_face_chrome(prev, hovered=False)

    def _on_canvas_click(self, event) -> None:
        fid = self._face_id_at(event.x, event.y)
        if fid is None:
            return
        if fid in self._selected_faces:
            self._selected_faces.discard(fid)
        else:
            self._selected_faces.add(fid)
        item = self._current_item()
        if item:
            self._draw_faces(item["members"])
        else:
            self._update_action_buttons()

    def _err(self, e: Exception) -> None:
        messagebox.showerror("Couldn't do that", str(e), parent=self.root)

    def _item_for_face_action(self) -> dict | None:
        item = self._current_item()
        if item is None:
            return None
        if item["kind"] == "track":
            return item
        return item

    def _do_name(self) -> None:
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or unassigned face"))
            return
        prompt = "What do you call this person?"
        name = simpledialog.askstring("Name person", prompt, parent=self.root)
        if not name:
            return
        try:
            apply_name(self.store, self.run_id, item, name)
        except (ReviewError, ReviewUiError) as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=False)
        self.status.config(text=NAME_SUCCESS_STATUS)

    def _do_merge(self) -> None:
        clusters_all = [
            it for it in (self.board.get("items") or []) if it["kind"] == "cluster"
        ]
        if len(clusters_all) < 2:
            self._err(ReviewUiError("need at least two groups to merge"))
            return
        selected = cluster_items_at_indices(self._visible_items, self._sel_indices)
        if len(selected) >= 2:
            self._open_visual_merge_confirm(selected[0], selected[1:])
            return
        self._open_visual_merge_picker(clusters_all)

    def _fill_merge_panel(
        self, parent, item: dict, *, title: str, photos_bucket: list
    ) -> None:
        """Draw a titled face strip for one group inside a merge dialog."""
        frame = ttk.Frame(parent, padding=8)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        ttk.Label(frame, text=title, font=_FONT_UI_BOLD).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text=item_label(item, detail=self._detail_mode),
            font=_FONT_UI,
            wraplength=260,
            foreground=INK_SECONDARY,
        ).pack(anchor=tk.W, pady=(2, 6))
        strip = tk.Canvas(
            frame, background=BG_DARK, height=MERGE_THUMB + 16, highlightthickness=0
        )
        strip.pack(fill=tk.X)
        reps = representative_members(item, MERGE_REPR_FACES)
        if not reps:
            strip.create_text(
                12, 12, anchor=tk.NW, fill=INK_ON_DARK, text="No faces", font=_FONT_UI
            )
            return
        x = 8
        placeholders = []
        for m in reps:
            rect = strip.create_rectangle(
                x, 8, x + MERGE_THUMB, 8 + MERGE_THUMB, fill="#444", outline="#888"
            )
            placeholders.append((m, x, 8, rect))
            x += MERGE_THUMB + 8
        strip.configure(scrollregion=(0, 0, x + 8, MERGE_THUMB + 16))

        def worker() -> None:
            results = []
            for m, sx, sy, rect in placeholders:
                b64 = crop_png_b64(
                    m["path"],
                    m["bbox"],
                    max_side=MERGE_THUMB,
                    frame_id=m.get("frame_id"),
                    source_type=m.get("source_type"),
                )
                results.append((sx, sy, rect, b64))

            def apply() -> None:
                for sx, sy, rect, b64 in results:
                    if b64 is None:
                        strip.create_text(
                            sx + MERGE_THUMB / 2,
                            sy + MERGE_THUMB / 2,
                            text="?",
                            fill="#ccc",
                        )
                        continue
                    try:
                        photo = tk.PhotoImage(data=b64)
                    except tk.TclError:
                        continue
                    photos_bucket.append(photo)
                    strip.delete(rect)
                    strip.create_image(sx, sy, anchor=tk.NW, image=photo)

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _open_visual_merge_confirm(self, keep: dict, others: list[dict]) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Merge groups")
        dlg.transient(self.root)
        dlg.minsize(640, 280)
        self._merge_photos = []
        ttk.Label(
            dlg,
            text="Look at both sides. Merge only if these are the same person.",
            font=_FONT_UI,
            wraplength=600,
        ).pack(anchor=tk.W, padx=12, pady=(12, 4))
        panes = ttk.Frame(dlg)
        panes.pack(fill=tk.BOTH, expand=True, padx=6)
        self._fill_merge_panel(
            panes, keep, title="Keep this group", photos_bucket=self._merge_photos
        )
        for o in others:
            self._fill_merge_panel(
                panes, o, title="Merge into it", photos_bucket=self._merge_photos
            )

        def ok() -> None:
            ids = [keep["cluster_id"]] + [o["cluster_id"] for o in others]
            try:
                apply_merge(self.store, self.run_id, ids)
            except ReviewError as e:
                messagebox.showerror("Couldn't merge", str(e), parent=dlg)
                return
            dlg.destroy()
            self.reload(invalidate_tracks=True)

        btns = ttk.Frame(dlg, padding=12)
        btns.pack(fill=tk.X)
        _review_button(btns, "Merge groups", ok, kind="primary").pack(side=tk.LEFT)
        _review_button(btns, "Cancel", dlg.destroy, kind="secondary").pack(side=tk.RIGHT)

    def _open_visual_merge_picker(self, clusters: list[dict]) -> None:
        """Pick keep + merge-ins with face strips (no text-only dropdown)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Merge groups")
        dlg.transient(self.root)
        dlg.geometry("720x520")
        dlg.minsize(640, 420)
        self._merge_photos = []
        ttk.Label(
            dlg,
            text="Choose the group to keep, then the group(s) to merge into it.",
            font=_FONT_UI,
            wraplength=680,
        ).pack(anchor=tk.W, padx=12, pady=(12, 4))

        keep_var = tk.IntVar(value=0)
        merge_vars: list[tk.BooleanVar] = []

        body = ttk.Frame(dlg)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        canvas = tk.Canvas(body, background=BG_SUBTLE, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def _on_inner_configure(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_inner_configure)

        for i, cl in enumerate(clusters):
            row = ttk.Frame(inner, padding=6)
            row.pack(fill=tk.X, pady=2)
            ttk.Radiobutton(row, text="Keep", variable=keep_var, value=i).pack(
                side=tk.LEFT, padx=(0, 8)
            )
            mv = tk.BooleanVar(value=False)
            merge_vars.append(mv)
            ttk.Checkbutton(row, text="Merge in", variable=mv).pack(
                side=tk.LEFT, padx=(0, 8)
            )
            self._fill_merge_panel(
                row,
                cl,
                title=item_label(cl, detail=False),
                photos_bucket=self._merge_photos,
            )

        def ok() -> None:
            keep_i = int(keep_var.get())
            if keep_i < 0 or keep_i >= len(clusters):
                messagebox.showerror(
                    "Couldn't merge", "Pick the group to keep.", parent=dlg
                )
                return
            others = [
                clusters[i]
                for i, v in enumerate(merge_vars)
                if v.get() and i != keep_i
            ]
            if not others:
                messagebox.showerror(
                    "Couldn't merge",
                    "Select at least one group to merge into it.",
                    parent=dlg,
                )
                return
            dlg.destroy()
            self._open_visual_merge_confirm(clusters[keep_i], others)

        btns = ttk.Frame(dlg, padding=12)
        btns.pack(fill=tk.X)
        _review_button(btns, "Review merge…", ok, kind="primary").pack(side=tk.LEFT)
        _review_button(btns, "Cancel", dlg.destroy, kind="secondary").pack(side=tk.RIGHT)

    def _do_split(self) -> None:
        item = self._current_item()
        if item is None or item["kind"] != "cluster":
            self._err(ReviewUiError("select a cluster and click faces to split off"))
            return
        if not self._selected_faces:
            self._err(ReviewUiError("click one or more faces in the cluster to split"))
            return
        try:
            apply_split(
                self.store,
                self.run_id,
                item["cluster_id"],
                sorted(self._selected_faces),
            )
        except ReviewError as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=True)

    def _do_ignore(self) -> None:
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or face"))
            return
        if item["kind"] == "track":
            self._err(ReviewUiError("click a face in the video to Ignore (a track is not a person)"))
            return
        if not messagebox.askyesno(
            "Ignore",
            "Mark as not a person / ignore? This writes a decision and hides the item from the board.",
            parent=self.root,
        ):
            return
        try:
            apply_ignore(self.store, self.run_id, item)
        except ReviewError as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=item["kind"] != "cluster")

    def _do_rule_out(self) -> None:
        """Durable Ruled out (not Ignore). Gated by SEMBLON_RULED_OUT (default ON)."""
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or face"))
            return
        if item["kind"] == "track":
            self._err(
                ReviewUiError("click a face in the video to Rule out (a track is not a person)")
            )
            return
        if not messagebox.askyesno(
            "Rule out",
            "Mark that this is not the suggested person?\n\n"
            "This keeps the faces visible as rejected. "
            "It is not the same as Ignore (which hides them as not a person).",
            parent=self.root,
        ):
            return
        try:
            apply_rule_out(self.store, self.run_id, item)
        except ReviewError as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=False)

    def _do_note(self) -> None:
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or face"))
            return
        if item["kind"] == "track":
            self._err(ReviewUiError("click a face in the video to Note (a track is not a person)"))
            return
        text = simpledialog.askstring("Note", "Review note:", parent=self.root)
        if not text:
            return
        try:
            apply_note(self.store, self.run_id, item, text)
        except ReviewError as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=False)

    def run(self) -> None:
        if self._owns_loop:
            self.root.mainloop()


def run_review_ui(
    store: Path | None = None,
    run_id: str | None = None,
    *,
    parent=None,
    on_add_folder: Callable[[], None] | None = None,
) -> dict:
    """Open Review. Expected empty (no store / no runs) shows coaching UI, not Error.

    Prefers the shared Cluster Review chrome host when a WebView is available;
    otherwise falls back to the tk ReviewApp and still writes the new review.html.
    """
    store_path = Path(store) if store is not None else default_store_path()
    try:
        rid = resolve_run_id(store_path, run_id)
    except ReviewExpectedEmpty as empty:
        app = ReviewApp(
            store_path,
            None,
            parent=parent,
            empty_reason=empty.reason,
            on_add_folder=on_add_folder,
        )
        app.run()
        store_out = (
            str(store_path.resolve()) if store_path.exists() else str(store_path)
        )
        return {"store": store_out, "run_id": None, "empty": True, "reason": empty.reason}

    # Shared chrome host (WebView when present; tk fallback + snapshot HTML).
    try:
        from semblon.review_chrome.host import host_review_chrome

        return host_review_chrome(
            store_path,
            rid,
            parent=parent,
            on_add_folder=on_add_folder,
        )
    except Exception:
        # Absolute last resort: tk only (host already logs WebView miss).
        app = ReviewApp(
            store_path, rid, parent=parent, on_add_folder=on_add_folder
        )
        app.run()
        return {"store": str(store_path.resolve()), "run_id": rid}
