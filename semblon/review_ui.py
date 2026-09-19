"""S8 Interactive Review slice — tkinter over existing review APIs.

Clusters are evidence. People exist only after an explicit Name action.
Does not retune clustering. Does not identify. Static review.html stays read-only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.export import STRONG_MIN_INTRA
from semblon.process import default_store_path, empty_state_line, latest_run_id
from semblon.tracks import TracksError, derive_tracks
from semblon.review import (
    ReviewError,
    ignore_subject,
    merge_clusters,
    name_cluster,
    name_face,
    name_faces,
    note_subject,
    split_cluster,
)
from semblon.store import connect, init_db

THUMB_MAX = 96

tk = ttk = messagebox = simpledialog = None


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


def resolve_run_id(store: Path, run_id: str | None) -> str:
    """Use --run when given; otherwise the latest run that still has faces.

    Empty incremental runs (FACE-005 skip-all) must not hide a prior populated run.
    """
    store = Path(store)
    if not store.is_file():
        raise ReviewUiError(f"store not found: {store}")
    if run_id:
        conn = connect(store)
        init_db(conn)
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
    return (path or "").replace("\\", "/").rstrip("/").split("/")[-1] or path or ""


def _track_items(
    store: Path, run_id: str, video_faces: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Render derived S7 tracks. Leftovers stay untracked observations."""
    if not video_faces:
        return [], []
    try:
        rec = derive_tracks(store, run_id)
    except TracksError:
        return [], list(video_faces)
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
                "note": "temporal association; not a person",
            }
        )
    leftover = [f for f in video_faces if f["face_id"] not in used]
    return items, leftover


def load_board(
    store: Path,
    run_id: str,
    *,
    strong_min_intra: float = STRONG_MIN_INTRA,
) -> dict:
    """Read-only board for the review UI. Does not enrol anyone."""
    store = Path(store)
    conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
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

    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    for f in faces:
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
        }
        if f["cluster_id"]:
            by_cluster.setdefault(f["cluster_id"], []).append(rec)
        elif f["status"] == "ok":
            unassigned.append(rec)

    items: list[dict] = []
    for c in clusters:
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

    track_items, leftover_video = _track_items(store, run_id, video_unassigned)
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
            "clusters": len(clusters),
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
            "unassigned_media": len({u["media_id"] for u in video_unassigned}),
            "named_persons": len(persons),
            "decisions": len(decisions),
            "faces": len(faces),
            "ok": sum(1 for f in faces if f["status"] == "ok"),
        },
        "empty_state": empty_state_line(store, run_id),
    }
    conn.close()
    return board


def crop_png_b64(
    path: str,
    bbox,
    max_side: int = THUMB_MAX,
    *,
    frame_id: int | None = None,
    source_type: str | None = None,
) -> str | None:
    """Face crop as base64 PNG for tk.PhotoImage (no PIL required).

    Stills: imread path. Video: seek ``frame_id`` then crop. No on-disk crops.
    """
    try:
        import base64

        import cv2
    except ImportError:
        return None
    from semblon.temporal import read_bgr

    # Video media must seek; stills use imread (frame_id ignored).
    if source_type == "video":
        if frame_id is None:
            return None
        img = read_bgr(path, int(frame_id))
    else:
        img = read_bgr(path, None)
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
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def crop_jpeg_bytes(
    path: str,
    bbox,
    max_side: int = THUMB_MAX,
    *,
    frame_id: int | None = None,
    source_type: str | None = None,
) -> bytes | None:
    """JPEG bytes for tests / non-tk consumers."""
    b64 = crop_png_b64(
        path, bbox, max_side=max_side, frame_id=frame_id, source_type=source_type
    )
    if b64 is None:
        return None
    import base64

    return base64.b64decode(b64)


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
    if item["kind"] == "unassigned_media" and not fid:
        raise ReviewUiError("click a face in the video to Name (a file is not a person)")
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
    if item["kind"] in ("track", "unassigned_media") and not fid:
        raise ReviewUiError("click a face in the video to Ignore (a track is not a person)")
    return ignore_subject(
        store, run_id, face_id=fid, disposition=disposition or "singleton"
    )


def apply_note(store: Path, run_id: str, item: dict, text: str) -> dict:
    if item["kind"] == "cluster":
        return note_subject(store, run_id, cluster_id=item["cluster_id"], text=text)
    fid = item.get("face_id")
    if item["kind"] in ("track", "unassigned_media") and not fid:
        raise ReviewUiError("click a face in the video to Note (a track is not a person)")
    return note_subject(store, run_id, face_id=fid, text=text)


def item_label(item: dict) -> str:
    if item["kind"] == "track":
        name = _basename(item.get("path") or "")
        tag = f" named:{','.join(item['person_names'])}" if item["named"] else " unnamed"
        t0 = item.get("t_ms_start")
        t1 = item.get("t_ms_end")
        return f"TRACK {name}  n={item['face_count']}  t={t0}-{t1}ms{tag}"
    if item["kind"] == "unassigned_media":
        name = _basename(item.get("path") or "")
        tag = f" named:{','.join(item['person_names'])}" if item["named"] else " unnamed"
        return f"VIDEO {name}  n={item['face_count']}{tag}"
    if item["kind"] == "unassigned":
        fid = item["face_id"][:8]
        tag = f" named:{item['person_names'][0]}" if item["named"] else " unnamed"
        return f"UNASSIGNED {fid}{tag}"
    cid = item["cluster_id"][:8]
    band = item["band"].upper()
    named = (
        f" person={','.join(item['person_names'])}"
        if item["named"]
        else " unnamed"
    )
    mi = "—" if item["min_intra"] is None else f"{item['min_intra']:.3f}"
    return f"{band} {cid}  n={item['face_count']}  min_intra={mi}{named}"


class ReviewApp:
    """Minimal tkinter surface. All mutations go through review.py."""

    def __init__(self, store: Path, run_id: str):
        _ensure_tk()
        self.store = Path(store)
        self.run_id = run_id
        self.board = load_board(self.store, self.run_id)
        self._photos: list = []
        self._selected_faces: set[str] = set()

        self.root = tk.Tk()
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
        ttk.Button(actions, text="Reload", command=self.reload).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Close", command=self.root.destroy).pack(side=tk.RIGHT, padx=2)
        self._review_actions = (
            self.btn_name,
            self.btn_merge,
            self.btn_split,
            self.btn_ignore,
            self.btn_note,
        )

        self.reload()

    def reload(self) -> None:
        self.board = load_board(self.store, self.run_id)
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
        has_items = bool(self.board["items"])
        state = tk.NORMAL if has_items else tk.DISABLED
        for btn in self._review_actions:
            btn.configure(state=state)
        self._draw_faces([])
        if not has_items:
            self.canvas.create_text(
                12,
                12,
                anchor=tk.NW,
                fill="#ccc",
                text="Nothing to review on this run. Open a populated run or process a folder.",
            )

    def _current_item(self) -> dict | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.board["items"][sel[0]]

    def _on_select(self, _event=None) -> None:
        item = self._current_item()
        self._selected_faces.clear()
        if item is None:
            self._draw_faces([])
            return
        self._draw_faces(item["members"])

    def _draw_faces(self, members: list[dict]) -> None:
        self.canvas.delete("all")
        if not members and self.board.get("items"):
            self.canvas.create_text(
                12,
                12,
                anchor=tk.NW,
                fill="#ccc",
                text="Select a cluster, track, or unassigned face.",
            )
        self._photos = []
        x, y = 8, 8
        row_h = THUMB_MAX + 28
        for m in members:
            jpeg = crop_png_b64(
                m["path"],
                m["bbox"],
                frame_id=m.get("frame_id"),
                source_type=m.get("source_type"),
            )
            photo = None
            if jpeg:
                try:
                    photo = tk.PhotoImage(data=jpeg)
                except tk.TclError:
                    photo = None
            tag = f"face:{m['face_id']}"
            if photo is not None:
                self._photos.append(photo)
                self.canvas.create_image(x, y, anchor=tk.NW, image=photo, tags=(tag,))
                tw, th = photo.width(), photo.height()
            else:
                tw = th = THUMB_MAX
                self.canvas.create_rectangle(
                    x, y, x + tw, y + th, fill="#444", outline="#888", tags=(tag,)
                )
                self.canvas.create_text(
                    x + tw / 2,
                    y + th / 2,
                    text="file missing",
                    fill="#ccc",
                    tags=(tag,),
                )
            mark = "*" if m["face_id"] in self._selected_faces else " "
            label = f"{mark}{m['face_id'][:8]}"
            if m.get("source_type") == "video":
                label += f" f={m.get('frame_id')}"
            self.canvas.create_text(
                x, y + th + 2, anchor=tk.NW, fill="#eee", text=label, tags=(tag,)
            )
            x += tw + 12
            if x > 700:
                x = 8
                y += row_h

    def _on_canvas_click(self, event) -> None:
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
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
        if item["kind"] == "unassigned_media":
            if len(self._selected_faces) == 1:
                return {**item, "face_id": next(iter(self._selected_faces))}
            if len(item["members"]) == 1:
                return {**item, "face_id": item["members"][0]["face_id"]}
            raise ReviewUiError("click one face in the video (a file is not a person)")
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
        if item["kind"] == "cluster" and item["band"] == "strong" and not item["named"]:
            # Explicit reminder — STRONG still requires Name.
            pass
        name = simpledialog.askstring(
            "Name person",
            "Display name (creates/links a person; STRONG is not auto-named):",
            parent=self.root,
        )
        if not name:
            return
        try:
            apply_name(self.store, self.run_id, item, name)
        except (ReviewError, ReviewUiError) as e:
            self._err(e)
            return
        self.reload()

    def _do_merge(self) -> None:
        clusters = [it for it in self.board["items"] if it["kind"] == "cluster"]
        if len(clusters) < 2:
            self._err(ReviewUiError("need at least two clusters to merge"))
            return
        labels = [item_label(it) for it in clusters]
        dlg = tk.Toplevel(self.root)
        dlg.title("Merge clusters")
        dlg.transient(self.root)
        ttk.Label(dlg, text="Survivor first, then donors (Ctrl+click multi-select):").pack(
            anchor=tk.W, padx=6, pady=4
        )
        lb = tk.Listbox(dlg, selectmode=tk.EXTENDED, width=80, height=16)
        for lab in labels:
            lb.insert(tk.END, lab)
        lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        def ok():
            sel = lb.curselection()
            if len(sel) < 2:
                messagebox.showerror("Merge", "select survivor + at least one donor", parent=dlg)
                return
            ids = [clusters[i]["cluster_id"] for i in sel]
            try:
                apply_merge(self.store, self.run_id, ids)
            except ReviewError as e:
                messagebox.showerror("Merge", str(e), parent=dlg)
                return
            dlg.destroy()
            self.reload()

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
        self.reload()

    def _do_ignore(self) -> None:
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or face"))
            return
        if not messagebox.askyesno(
            "Ignore",
            "Mark as not a person / ignore? This writes a decision; it does not enrol.",
            parent=self.root,
        ):
            return
        try:
            apply_ignore(self.store, self.run_id, item)
        except ReviewError as e:
            self._err(e)
            return
        self.reload()

    def _do_note(self) -> None:
        try:
            item = self._item_for_face_action()
        except ReviewUiError as e:
            self._err(e)
            return
        if item is None:
            self._err(ReviewUiError("select a cluster or face"))
            return
        text = simpledialog.askstring("Note", "Review note:", parent=self.root)
        if not text:
            return
        try:
            apply_note(self.store, self.run_id, item, text)
        except ReviewError as e:
            self._err(e)
            return
        self.reload()

    def run(self) -> None:
        self.root.mainloop()


def run_review_ui(store: Path | None = None, run_id: str | None = None) -> dict:
    store_path = Path(store) if store is not None else default_store_path()
    rid = resolve_run_id(store_path, run_id)
    app = ReviewApp(store_path, rid)
    app.run()
    return {"store": str(store_path.resolve()), "run_id": rid}
