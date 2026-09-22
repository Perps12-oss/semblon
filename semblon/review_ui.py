"""S8 Interactive Review slice — tkinter over existing review APIs.

Clusters are evidence. People exist only after an explicit Name action.
Does not retune clustering. Does not identify. Static review.html stays read-only.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
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

tk = ttk = messagebox = simpledialog = None

# Bounded LRU caches for decoded frames and PNG crops (process-local).
_frame_cache: OrderedDict[tuple, object] = OrderedDict()
_crop_cache: OrderedDict[tuple, str] = OrderedDict()
_frame_lock = threading.Lock()


def _ensure_tk() -> None:
    """Load tkinter only when the window runs. Board/API stay headless."""
    global tk, ttk, messagebox, simpledialog
    if tk is not None:
        return
    import tkinter as _tk
    from tkinter import messagebox as _mb
    from tkinter import simpledialog as _sd
    from tkinter import ttk as _ttk

    tk = _tk
    ttk = _ttk
    messagebox = _mb
    simpledialog = _sd


class ReviewUiError(ValueError):
    pass


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
    """
    store = Path(store)
    if not store.is_file():
        raise ReviewUiError(f"store not found: {store}")
    if run_id:
        conn = _ro_connect(store)
        row = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        conn.close()
        if row is None:
            raise ReviewUiError(f"unknown run: {run_id}")
        return run_id
    rid = latest_run_id(store, with_faces=True) or latest_run_id(store)
    if rid is None:
        raise ReviewUiError("store has no runs")
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


def item_label(item: dict) -> str:
    note_tag = " [note]" if item.get("has_note") else ""
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

    def __init__(self, store: Path, run_id: str, *, parent=None):
        _ensure_tk()
        self.store = Path(store)
        self.run_id = run_id
        self._tracks_cache: dict | None = None
        self.board = load_board(self.store, self.run_id)
        self._tracks_cache = self.board.get("_tracks_cache")
        self._photos: list = []
        self._selected_faces: set[str] = set()
        self._draw_gen = 0

        self.root, self._owns_loop = make_review_root(parent)
        self.root.title(f"Semblon Review — {self.run_id}")
        self.root.geometry("980x640")

        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text=(
                "S8 Interactive Review. Clusters are evidence. "
                "STRONG is not a person until you Name."
            ),
        ).pack(anchor=tk.W)
        self.empty_state = ttk.Label(top, text="")
        self.empty_state.pack(anchor=tk.W)
        self.status = ttk.Label(top, text="")
        self.status.pack(anchor=tk.W)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=3)

        ttk.Label(left, text="Clusters / tracks / unassigned").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left, exportselection=False)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        ttk.Label(right, text="Faces (click to toggle for Split)").pack(anchor=tk.W)
        self.canvas = tk.Canvas(right, background="#222", height=420)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        actions = ttk.Frame(self.root, padding=6)
        actions.pack(fill=tk.X)
        self.btn_name = ttk.Button(actions, text="Name", command=self._do_name)
        self.btn_name.pack(side=tk.LEFT, padx=2)
        self.btn_merge = ttk.Button(actions, text="Merge…", command=self._do_merge)
        self.btn_merge.pack(side=tk.LEFT, padx=2)
        self.btn_split = ttk.Button(actions, text="Split selected", command=self._do_split)
        self.btn_split.pack(side=tk.LEFT, padx=2)
        self.btn_ignore = ttk.Button(actions, text="Ignore", command=self._do_ignore)
        self.btn_ignore.pack(side=tk.LEFT, padx=2)
        self.btn_note = ttk.Button(actions, text="Note…", command=self._do_note)
        self.btn_note.pack(side=tk.LEFT, padx=2)
        self.btn_rule_out = ttk.Button(
            actions, text="Rule out…", command=self._do_rule_out
        )
        self.btn_rule_out.pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Reload", command=self.reload).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Close", command=self.root.destroy).pack(side=tk.RIGHT, padx=2)
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

        self.reload()

    def reload(self, *, invalidate_tracks: bool = True) -> None:
        if invalidate_tracks:
            self._tracks_cache = None
        self.board = load_board(
            self.store, self.run_id, tracks_cache=self._tracks_cache
        )
        self._tracks_cache = self.board.get("_tracks_cache")
        self.listbox.delete(0, tk.END)
        for item in self.board["items"]:
            self.listbox.insert(tk.END, item_label(item))
        c = self.board["counts"]
        self.empty_state.config(text=self.board.get("empty_state") or "")
        self.status.config(
            text=(
                f"store={self.store}  run={self.run_id}  "
                f"review={c['review_required']} strong={c['strong']} "
                f"unassigned={c['unassigned']} tracks={c.get('tracks', 0)} "
                f"untracked={c.get('untracked', 0)} "
                f"persons={c['named_persons']} "
                f"decisions={c['decisions']}"
            )
        )
        self._selected_faces.clear()
        self._update_action_buttons()
        self._set_empty_canvas(
            "Nothing to review on this run. Open a populated run or process a folder."
            if not self.board["items"]
            else "Select a cluster, track, or unassigned face."
        )

    def _set_empty_canvas(self, text: str) -> None:
        self.canvas.delete("all")
        self._photos = []
        self.canvas.create_text(12, 12, anchor=tk.NW, fill="#ccc", text=text)

    def _update_action_buttons(self) -> None:
        item = self._current_item()
        if item is None:
            flags = _actions_for_kind("")
            if self.board["items"]:
                # No selection: Name/Merge may still open dialogs that pick items.
                flags = {"name": False, "merge": True, "split": False, "ignore": False, "note": False}
        else:
            flags = _actions_for_kind(item["kind"])
        for key, btn in self._btn_map.items():
            btn.configure(state=tk.NORMAL if flags.get(key) else tk.DISABLED)

    def _current_item(self) -> dict | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.board["items"][sel[0]]

    def _on_select(self, _event=None) -> None:
        item = self._current_item()
        self._selected_faces.clear()
        self._update_action_buttons()
        if item is None:
            self._set_empty_canvas("Select a cluster, track, or unassigned face.")
            return
        self._draw_faces(item["members"])

    def _draw_faces(self, members: list[dict]) -> None:
        self._draw_gen += 1
        gen = self._draw_gen
        self.canvas.delete("all")
        self._photos = []
        if not members:
            self._set_empty_canvas("Select a cluster, track, or unassigned face.")
            return
        # Placeholders first; fill crops asynchronously.
        x, y = 8, 8
        row_h = THUMB_MAX + 28
        slots = []
        for m in members:
            tw = th = THUMB_MAX
            tag = f"face:{m['face_id']}"
            rect = self.canvas.create_rectangle(
                x, y, x + tw, y + th, fill="#444", outline="#888", tags=(tag,)
            )
            mark = "*" if m["face_id"] in self._selected_faces else " "
            label = f"{mark}{m['face_id'][:8]}"
            if m.get("source_type") == "video":
                label += f" f={m.get('frame_id')}"
            self.canvas.create_text(
                x, y + th + 2, anchor=tk.NW, fill="#eee", text=label, tags=(tag,)
            )
            slots.append((m, x, y, rect, tag))
            x += tw + 12
            if x > 700:
                x = 8
                y += row_h

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

    def _apply_crops(self, gen: int, results) -> None:
        if gen != self._draw_gen:
            return
        for m, x, y, rect, tag, b64 in results:
            if b64 is None:
                self.canvas.create_text(
                    x + THUMB_MAX / 2,
                    y + THUMB_MAX / 2,
                    text="file missing",
                    fill="#ccc",
                    tags=(tag,),
                )
                continue
            try:
                photo = tk.PhotoImage(data=b64)
            except tk.TclError:
                continue
            self._photos.append(photo)
            self.canvas.delete(rect)
            self.canvas.create_image(x, y, anchor=tk.NW, image=photo, tags=(tag,))

    def _on_canvas_click(self, event) -> None:
        items = self.canvas.find_overlapping(
            event.x - 1, event.y - 1, event.x + 1, event.y + 1
        )
        for it in items:
            for tag in self.canvas.gettags(it):
                if tag.startswith("face:"):
                    fid = tag.split(":", 1)[1]
                    if fid in self._selected_faces:
                        self._selected_faces.discard(fid)
                    else:
                        self._selected_faces.add(fid)
                    item = self._current_item()
                    if item:
                        self._draw_faces(item["members"])
                    return

    def _err(self, e: Exception) -> None:
        messagebox.showerror("Semblon Review", str(e), parent=self.root)

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
        prompt = "Display name (creates a new person; STRONG is not auto-named):"
        if item["kind"] == "cluster" and item["band"] == "strong" and not item["named"]:
            prompt = (
                "STRONG cluster — Name creates a person (not automatic).\n"
                "Display name:"
            )
        name = simpledialog.askstring("Name person", prompt, parent=self.root)
        if not name:
            return
        try:
            apply_name(self.store, self.run_id, item, name)
        except (ReviewError, ReviewUiError) as e:
            self._err(e)
            return
        self.reload(invalidate_tracks=False)

    def _do_merge(self) -> None:
        clusters = [it for it in self.board["items"] if it["kind"] == "cluster"]
        if len(clusters) < 2:
            self._err(ReviewUiError("need at least two clusters to merge"))
            return
        labels = [item_label(it) for it in clusters]
        dlg = tk.Toplevel(self.root)
        dlg.title("Merge clusters")
        dlg.transient(self.root)
        ttk.Label(dlg, text="Survivor (kept cluster id):").pack(anchor=tk.W, padx=6, pady=4)
        survivor_var = tk.StringVar(value=labels[0])
        ttk.Combobox(
            dlg, textvariable=survivor_var, values=labels, state="readonly", width=80
        ).pack(fill=tk.X, padx=6, pady=2)
        ttk.Label(dlg, text="Donors (Ctrl+click multi-select):").pack(
            anchor=tk.W, padx=6, pady=4
        )
        lb = tk.Listbox(dlg, selectmode=tk.EXTENDED, width=80, height=14)
        for lab in labels:
            lb.insert(tk.END, lab)
        lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        def ok():
            survivor_label = survivor_var.get()
            if survivor_label not in labels:
                messagebox.showerror("Merge", "pick a survivor", parent=dlg)
                return
            survivor_i = labels.index(survivor_label)
            sel = [i for i in lb.curselection() if i != survivor_i]
            if not sel:
                messagebox.showerror("Merge", "select at least one donor", parent=dlg)
                return
            ids = [clusters[survivor_i]["cluster_id"]] + [
                clusters[i]["cluster_id"] for i in sel
            ]
            try:
                apply_merge(self.store, self.run_id, ids)
            except ReviewError as e:
                messagebox.showerror("Merge", str(e), parent=dlg)
                return
            dlg.destroy()
            self.reload(invalidate_tracks=True)

        ttk.Button(dlg, text="Merge", command=ok).pack(side=tk.LEFT, padx=6, pady=6)
        ttk.Button(dlg, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT, padx=6, pady=6)

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
            "Record a durable Ruled out decision? This is not Ignore — "
            "the observation stays visible as rejected.",
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
) -> dict:
    store_path = Path(store) if store is not None else default_store_path()
    rid = resolve_run_id(store_path, run_id)
    app = ReviewApp(store_path, rid, parent=parent)
    app.run()
    return {"store": str(store_path.resolve()), "run_id": rid}
