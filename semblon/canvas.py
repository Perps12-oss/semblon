"""Observation overlay data + production Canvas workspace.

Draws boxes/tracks from persisted observations. Not identity and not the final
R3 native shell. Never writes faces.person_id. Cluster ≠ person; track ≠ person.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.process import default_store_path, latest_run_id

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:  # pragma: no cover - depends on host Python build
    tk = None
    ttk = None


class CanvasError(ValueError):
    pass


CANVAS_NOTE = (
    "Canvas overlays observations. Face identity stays FaceKit. "
    "Canvas never writes faces.person_id. Track ≠ person. Cluster ≠ person."
)


def face_evidence_tag(face: dict) -> str:
    """Evidence-axis label for a face box. Does not read person_id for chrome."""
    if face.get("cluster_id"):
        return "clustered"
    return "unassigned"


def load_canvas(store: Path, run_id: str | None = None) -> dict:
    """Overlay payload: media + boxes + persisted track lanes. Cluster ≠ person."""
    store = Path(store)
    if not store.is_file():
        raise CanvasError(f"store not found: {store}")
    conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    rid = run_id or latest_run_id(store, with_faces=True) or latest_run_id(store)
    if rid is None:
        conn.close()
        raise CanvasError("store has no runs")
    try:
        media = conn.execute(
            """SELECT DISTINCT m.media_id, m.path, m.source_type
               FROM media m
               JOIN observations o ON o.media_id = m.media_id
               WHERE o.run_id=?
               ORDER BY m.path""",
            (rid,),
        ).fetchall()
        faces = conn.execute(
            """SELECT f.face_id, f.observation_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
                      f.status, f.cluster_id, f.person_id, o.media_id, o.frame_id, o.t_ms
               FROM faces f JOIN observations o ON o.observation_id=f.observation_id
               WHERE f.run_id=?""",
            (rid,),
        ).fetchall()
    except sqlite3.DatabaseError as e:
        conn.close()
        raise CanvasError(f"canvas load failed: {e}") from e
    warnings: list[str] = []
    items = []
    tracks = []
    track_members = []
    try:
        items = conn.execute(
            """SELECT i.item_id, i.kind, i.provider, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2,
                      i.score, i.payload_json, o.media_id
               FROM observation_items i JOIN observations o ON o.observation_id=i.observation_id
               WHERE i.run_id=?""",
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"items unavailable: {e}")
    try:
        tracks = conn.execute(
            "SELECT track_id, media_id, kind, t_ms_start, t_ms_end, item_count FROM tracks WHERE run_id=?",
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"tracks unavailable: {e}")
    try:
        track_members = conn.execute(
            """
            SELECT tm.track_id, tm.item_id, oi.face_id, oi.observation_id, o.media_id
            FROM track_members tm
            JOIN tracks t ON t.track_id = tm.track_id
            JOIN observation_items oi ON oi.item_id = tm.item_id
            JOIN observations o ON o.observation_id = oi.observation_id
            WHERE t.run_id=?
            """,
            (rid,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        warnings.append(f"track memberships unavailable: {e}")
    conn.close()
    lane_by_face: dict[str, str] = {}
    lane_by_item: dict[str, str] = {}
    for row in track_members:
        d = dict(row)
        lane_by_item[d["item_id"]] = d["track_id"]
        if d.get("face_id"):
            lane_by_face[d["face_id"]] = d["track_id"]
    note = CANVAS_NOTE
    if warnings:
        note = note + " " + " | ".join(warnings)
    return {
        "run_id": rid,
        "media": [dict(r) for r in media],
        "faces": [dict(r) for r in faces],
        "items": [
            {**dict(r), "payload": json.loads(r["payload_json"] or "{}")}
            for r in items
        ],
        "tracks": [dict(r) for r in tracks],
        "track_members": [dict(r) for r in track_members],
        "track_lane_by_face": lane_by_face,
        "track_lane_by_item": lane_by_item,
        "note": note,
    }


def overlay_boxes(board: dict, media_id: str) -> list[dict]:
    """Display boxes for one media. Never includes person_id in the payload."""
    boxes = []
    lane_by_face = board.get("track_lane_by_face") or {}
    lane_by_item = board.get("track_lane_by_item") or {}
    for f in board.get("faces") or []:
        if f.get("media_id") != media_id:
            continue
        lane = lane_by_face.get(f.get("face_id"))
        tag = face_evidence_tag(f)
        if lane:
            tag = f"{tag} lane={lane}"
        boxes.append(
            {
                "kind": "face",
                "id": f.get("face_id"),
                "bbox": [f.get("bbox_x1"), f.get("bbox_y1"), f.get("bbox_x2"), f.get("bbox_y2")],
                "tag": tag,
                "color": "#2e8b57",
            }
        )
    for it in board.get("items") or []:
        if it.get("media_id") != media_id or it.get("kind") == "face":
            continue
        if it.get("bbox_x1") is None:
            continue
        lane = lane_by_item.get(it.get("item_id"))
        tag = it.get("provider") or it.get("kind") or "item"
        if lane:
            tag = f"{tag} lane={lane}"
        boxes.append(
            {
                "kind": it.get("kind"),
                "id": it.get("item_id"),
                "bbox": [it.get("bbox_x1"), it.get("bbox_y1"), it.get("bbox_x2"), it.get("bbox_y2")],
                "tag": tag,
                "color": "#c47a1a",
            }
        )
    return boxes


def media_inspector_lines(board: dict, media_id: str | None) -> list[str]:
    """Inspector evidence lines for one media selection. Group ≠ person."""
    if not media_id:
        return [
            board.get("note") or CANVAS_NOTE,
            f"run={board.get('run_id')}",
            f"media={len(board.get('media') or [])}  faces={len(board.get('faces') or [])}",
        ]
    media = next((m for m in (board.get("media") or []) if m.get("media_id") == media_id), None)
    faces = [f for f in (board.get("faces") or []) if f.get("media_id") == media_id]
    items = [i for i in (board.get("items") or []) if i.get("media_id") == media_id]
    tracks = [t for t in (board.get("tracks") or []) if t.get("media_id") == media_id]
    clustered = sum(1 for f in faces if f.get("cluster_id"))
    unassigned = sum(1 for f in faces if not f.get("cluster_id"))
    lines = [
        f"path={media.get('path') if media else '?'}",
        f"source_type={media.get('source_type') if media else '?'}",
        f"faces={len(faces)}  clustered={clustered}  unassigned={unassigned}",
        f"items={len(items)}  tracks={len(tracks)}  (track ≠ person)",
        "Evidence: boxes/tracks only. Group ≠ person. Name happens in Review.",
        "Actions: Open Review · Merge observations ≠ Assign to person",
        CANVAS_NOTE,
    ]
    if not faces:
        lines.insert(3, "Zero faces — still Library (not failed ingest)")
    return lines


def _ppm_photo(img_bgr, max_side: int = 720):
    import cv2

    h, w = img_bgr.shape[:2]
    scale = min(1.0, float(max_side) / float(max(h, w, 1)))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    if (nw, nh) != (w, h):
        img_bgr = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".ppm", img_bgr)
    if not ok:
        raise ValueError("ppm encode failed")
    return buf.tobytes(), scale, nw, nh


if tk is None:
    class CanvasWorkspace:
        """Headless stub — tkinter required for embedded Canvas."""

        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("tkinter is required for canvas workspace")

else:
    class CanvasWorkspace:
        """Production-usable Tk Canvas workspace (embeddable in Home).

        Constructor matches Home shell:
          CanvasWorkspace(master, store=..., run_id=..., on_select=..., show_chrome=True)

        Never writes to the store. Overlay tags use evidence axis only.
        """

        def __init__(
            self,
            master,
            *,
            store: Path | None = None,
            run_id: str | None = None,
            on_select=None,
            show_chrome: bool = True,
            source_types: tuple[str, ...] | None = None,
        ):
            self.frame = ttk.Frame(master)
            self._on_select = on_select
            self._source_types = source_types
            self.board: dict | None = None
            self._media: list[dict] = []
            self._photo = None
            self.status = tk.StringVar(value="No board loaded")

            if show_chrome:
                ttk.Label(self.frame, textvariable=self.status, wraplength=520).pack(
                    anchor=tk.W, pady=(0, 4)
                )

            body = ttk.Frame(self.frame)
            body.pack(fill=tk.BOTH, expand=True)
            self._listbox = tk.Listbox(body, width=36, exportselection=False)
            self._listbox.pack(side=tk.LEFT, fill=tk.Y)
            self._listbox.bind("<<ListboxSelect>>", self._on_list_select)
            self.preview = tk.Canvas(body, background="#111", highlightthickness=0)
            self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

            if store is not None:
                try:
                    self.reload(store, run_id)
                except CanvasError as e:
                    self.status.set(str(e))

        def pack(self, **kwargs):
            return self.frame.pack(**kwargs)

        def pack_forget(self):
            return self.frame.pack_forget()

        def grid(self, **kwargs):
            return self.frame.grid(**kwargs)

        def reload(
            self,
            store: Path | None = None,
            run_id: str | None = None,
            *,
            source_types: tuple[str, ...] | None = None,
        ) -> None:
            if source_types is not None:
                self._source_types = source_types
            path = Path(store) if store is not None else None
            if path is None or not path.is_file():
                self.board = None
                self._media = []
                self._listbox.delete(0, tk.END)
                self.preview.delete("all")
                self.status.set("No store yet — Choose folder on Home.")
                if self._on_select is not None:
                    self._on_select(None, ["No store yet."])
                return
            board = load_canvas(path, run_id)
            media = list(board.get("media") or [])
            if self._source_types is not None:
                media = [m for m in media if (m.get("source_type") or "") in self._source_types]
            self.set_board(board, media)

        def set_board(self, board: dict, media_rows: list[dict] | None = None) -> None:
            self.board = board
            self._media = list(media_rows if media_rows is not None else board.get("media") or [])
            self._listbox.delete(0, tk.END)
            face_by: dict[str, int] = {}
            item_by: dict[str, int] = {}
            for f in board.get("faces") or []:
                face_by[f["media_id"]] = face_by.get(f["media_id"], 0) + 1
            for it in board.get("items") or []:
                item_by[it["media_id"]] = item_by.get(it["media_id"], 0) + 1
            for m in self._media:
                mid = m["media_id"]
                nface = face_by.get(mid, 0)
                nitem = item_by.get(mid, 0)
                z = " zero-face" if nface == 0 else ""
                self._listbox.insert(
                    tk.END,
                    f"{m.get('source_type')}  faces={nface} items={nitem}{z}  {m.get('path')}",
                )
            self.status.set(
                f"run={board.get('run_id')}  media={len(self._media)}  "
                f"faces={len(board.get('faces') or [])}  "
                f"tracks={len(board.get('tracks') or [])}"
            )
            if self._media:
                self._listbox.selection_set(0)
                self.show_index(0)
            else:
                self.preview.delete("all")
                lines = media_inspector_lines(board, None)
                if self._on_select is not None:
                    self._on_select(None, lines)

        def show_index(self, index: int) -> None:
            if index < 0 or index >= len(self._media):
                return
            self.show_media(self._media[index])

        def show_media(self, media: dict) -> None:
            if self.board is None:
                return
            mid = media.get("media_id")
            path = media.get("path")
            boxes = overlay_boxes(self.board, mid)
            lines = media_inspector_lines(self.board, mid)
            if self._on_select is not None:
                self._on_select(mid, lines)

            self.preview.delete("all")
            self._photo = None
            try:
                import cv2
            except ImportError as e:
                self.preview.create_text(
                    12, 12, anchor=tk.NW, fill="#ddd", text=f"OpenCV unavailable: {e}"
                )
                self.status.set(f"preview unavailable  {path}")
                return

            img = cv2.imread(str(path)) if path else None
            if img is None:
                self.preview.create_text(
                    12, 12, anchor=tk.NW, fill="#ddd", text=f"file missing\n{path}"
                )
                y = 48
                for box in boxes:
                    self.preview.create_text(
                        12,
                        y,
                        anchor=tk.NW,
                        fill=box["color"],
                        text=f"{box['kind']} {box['tag']} {box['bbox']}",
                    )
                    y += 16
                self.status.set(f"file missing  boxes={len(boxes)}  group ≠ person")
                return
            try:
                data, scale, nw, nh = _ppm_photo(img)
                photo = tk.PhotoImage(data=data)
            except Exception as e:  # noqa: BLE001 — preview is optional
                self.preview.create_text(
                    12,
                    12,
                    anchor=tk.NW,
                    fill="#ddd",
                    text=f"preview unavailable: {type(e).__name__}\n{path}",
                )
                self.status.set(f"preview unavailable  {path}")
                return
            self._photo = photo
            self.preview.create_image(0, 0, anchor=tk.NW, image=photo)
            self.preview.config(scrollregion=(0, 0, nw, nh))
            for box in boxes:
                x1, y1, x2, y2 = box["bbox"]
                if None in (x1, y1, x2, y2):
                    continue
                self.preview.create_rectangle(
                    x1 * scale,
                    y1 * scale,
                    x2 * scale,
                    y2 * scale,
                    outline=box["color"],
                    width=2,
                )
                self.preview.create_text(
                    x1 * scale + 4,
                    y1 * scale + 4,
                    anchor=tk.NW,
                    fill=box["color"],
                    text=f"{box['kind']} {box['tag']}",
                )
            self.status.set(f"{path}  boxes={len(boxes)}  group ≠ person")

        def _on_list_select(self, _evt=None) -> None:
            sel = self._listbox.curselection()
            if sel:
                self.show_index(int(sel[0]))


def run_canvas(store: Path | None = None, run_id: str | None = None, *, parent=None) -> int:
    """Standalone or Toplevel Canvas window (CLI `semblon canvas`)."""
    if tk is None or ttk is None:
        raise CanvasError("tkinter is required for canvas")

    own = parent is None
    root = tk.Tk() if own else tk.Toplevel(parent)
    board_note = CANVAS_NOTE
    try:
        board = load_canvas(store or default_store_path(), run_id)
        board_note = board.get("note") or CANVAS_NOTE
        rid = board.get("run_id")
    except CanvasError:
        rid = run_id
        board = None

    root.title(f"Semblon Canvas — {rid or '—'}")
    root.geometry("960x640")
    ttk.Label(root, text=board_note, wraplength=920).pack(anchor=tk.W, padx=8, pady=6)
    ws = CanvasWorkspace(
        root,
        store=store or default_store_path(),
        run_id=run_id,
        show_chrome=True,
    )
    ws.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    ttk.Button(root, text="Close", command=root.destroy).pack(pady=6)
    if own:
        root.mainloop()
    return 0
