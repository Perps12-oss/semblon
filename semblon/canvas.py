"""Observation overlay data + production Canvas workspace.

Photo-first: clean photograph by default. Overlays appear only on
hover / click / drag. Soft product copy lives in product_surface;
advanced dumps stay behind advanced=True. Canvas never writes
faces.person_id. Cluster ≠ person; track ≠ person.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.process import default_store_path, latest_run_id
from semblon.state_triple import (
    format_media_card_label,
    library_include_media,
    media_inspector_triple_line,
    triples_for_board,
)

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
    "Canvas never writes faces.person_id. Track ≠ person. Cluster ≠ person. "
    "Media cards expose Artifact 2 state triple (Ingest, Analysis, Identity)."
)


def face_evidence_tag(face: dict) -> str:
    """Evidence-axis label for a face box (R3-BRIEF). Does not read person_id."""
    from semblon.r3_chrome import face_evidence_label

    return face_evidence_label(face)


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
    decisions: list[dict] = []
    clusters: list[dict] = []
    persons: list[dict] = []
    run_finished = None
    try:
        decisions = [
            dict(r)
            for r in conn.execute(
                "SELECT kind, face_id, person_id, cluster_id, policy_json, run_id "
                "FROM decisions WHERE run_id=?",
                (rid,),
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"decisions unavailable: {e}")
    try:
        clusters = [
            dict(r)
            for r in conn.execute(
                "SELECT cluster_id, status FROM clusters WHERE run_id=?",
                (rid,),
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"clusters unavailable: {e}")
    try:
        persons = [
            dict(r)
            for r in conn.execute(
                "SELECT person_id, display_name FROM persons ORDER BY display_name"
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        warnings.append(f"persons unavailable: {e}")
    try:
        run_row = conn.execute(
            "SELECT finished_at FROM runs WHERE run_id=?", (rid,)
        ).fetchone()
        if run_row is not None:
            run_finished = run_row["finished_at"] is not None
    except sqlite3.OperationalError as e:
        warnings.append(f"run status unavailable: {e}")
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
        "decisions": decisions,
        "clusters": clusters,
        "persons": persons,
        "run_finished": run_finished,
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


def _cluster_status_map(board: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in board.get("clusters") or []:
        cid = c.get("cluster_id")
        if cid:
            out[str(cid)] = str(c.get("status") or "auto")
    return out


def media_state_triples(board: dict, media_rows: list[dict] | None = None) -> dict:
    """Artifact 2 triples for board media. Read-only; never writes person_id."""
    return triples_for_board(
        board,
        media_rows=media_rows,
        decisions=board.get("decisions"),
        cluster_status=_cluster_status_map(board),
        run_finished=board.get("run_finished"),
    )


def media_inspector_lines(board: dict, media_id: str | None) -> list[str]:
    """Inspector evidence lines for one media selection. Group ≠ person.

    Labels distinguish Evidence (machine) from Proposed action (human).
    Actual verb buttons live on Home Inspector; this is read-only chrome.
    """
    from semblon.r3_chrome import chrome_legend_lines, face_display_state

    if not media_id:
        return [
            "Evidence relationship (machine)",
            board.get("note") or CANVAS_NOTE,
            f"run={board.get('run_id')}",
            f"media={len(board.get('media') or [])}  faces={len(board.get('faces') or [])}",
            *chrome_legend_lines()[:3],
            "Proposed action (human): use Home Inspector verbs",
            "Merge observations ≠ Assign to person",
        ]
    media = next((m for m in (board.get("media") or []) if m.get("media_id") == media_id), None)
    faces = [f for f in (board.get("faces") or []) if f.get("media_id") == media_id]
    items = [i for i in (board.get("items") or []) if i.get("media_id") == media_id]
    tracks = [t for t in (board.get("tracks") or []) if t.get("media_id") == media_id]
    clustered = sum(1 for f in faces if f.get("cluster_id"))
    unassigned = sum(1 for f in faces if not f.get("cluster_id"))
    cluster_ids = sorted({f.get("cluster_id") for f in faces if f.get("cluster_id")})
    triples = media_state_triples(board, [media] if media else [])
    triple = triples.get(media_id) if media_id else None
    display_counts: dict[str, int] = {}
    for f in faces:
        label = face_display_state(f)
        display_counts[label] = display_counts.get(label, 0) + 1
    display_bits = "  ".join(f"{k}={v}" for k, v in sorted(display_counts.items())) or "none"
    lines = [
        "Evidence relationship (machine)",
        f"path={media.get('path') if media else '?'}",
        f"source_type={media.get('source_type') if media else '?'}",
        f"faces={len(faces)}  clustered={clustered}  unassigned={unassigned}",
        f"cluster membership: {', '.join(c[:12] for c in cluster_ids) or 'none'}",
        f"display: {display_bits}",
        f"items={len(items)}  tracks={len(tracks)}  (track ≠ person)",
        "Boxes/tracks only. Group ≠ person. Similarity is not identity.",
        "Proposed action (human): Home Inspector — Merge · Assign · Split · Name · Rule out · Ignore",
        "Merge observations ≠ Assign to person",
        CANVAS_NOTE,
    ]
    if triple is not None:
        # After source_type (index 2): Evidence, path, source, then triple.
        lines.insert(3, media_inspector_triple_line(triple))
    if not faces:
        # After faces= line: index 4 without triple; index 5 when triple shifted faces.
        insert_at = 5 if triple is not None else 4
        lines.insert(insert_at, "Zero faces — still Library (not failed ingest)")
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


def _ppm_thumb(path: str | None, *, max_side: int = 88):
    """Small PPM thumbnail for the Photos strip. Returns None if unloadable."""
    if not path:
        return None
    try:
        import cv2
    except ImportError:
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    try:
        data, _scale, nw, nh = _ppm_photo(img, max_side=max_side)
    except Exception:  # noqa: BLE001
        return None
    return data, nw, nh


if tk is None:
    class CanvasWorkspace:
        """Headless stub — tkinter required for embedded Canvas."""

        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("tkinter is required for canvas workspace")

else:
    class CanvasWorkspace:
        """Photo-first Canvas workspace (embeddable in Home).

        DEFAULT: clean photograph (no permanent boxes/labels).
        HOVER: subtle outline on one observation under the pointer.
        CLICK: select that observation → soft Inspector copy.
        DRAG: rubber-band any region → hit-test stored observations.
        ESC / click empty: dismiss overlays.

        Never writes to the store. Detection data remains in the board.
        """

        _DRAG_THRESHOLD = 6
        # Interaction accents — not CV class colours (no orange=object / green=face).
        _HOVER_COLOR = "#9B96EC"
        _SELECT_COLOR = "#4338CA"
        _DRAG_COLOR = "#C4C0FF"
        _THUMB_COLS = 2
        _THUMB_CELL = 96
        _THUMB_PAD = 6

        def __init__(
            self,
            master,
            *,
            store: Path | None = None,
            run_id: str | None = None,
            on_select=None,
            show_chrome: bool = True,
            source_types: tuple[str, ...] | None = None,
            advanced: bool = False,
        ):
            from semblon.ui_tokens import ACCENT, BG_DARK, BG_SUBTLE, CAPTION, INK_ON_DARK, INK_SECONDARY

            self.frame = ttk.Frame(master)
            self._on_select = on_select
            self._source_types = source_types
            self._advanced = bool(advanced)
            self.board: dict | None = None
            self._media: list[dict] = []
            self._photo = None
            self._scale = 1.0
            self._nw = 0
            self._nh = 0
            self._current_media: dict | None = None
            self._hit_regions: list[dict] = []  # display-space hits
            self._hover_id: str | None = None
            self._selected: dict | None = None
            self._drag_origin: tuple[float, float] | None = None
            self._drag_rect_id = None
            self._drag_active = False
            self._tip_shown = True
            self._thumb_photos: list = []  # keep PhotoImage refs alive
            self._thumb_hitmap: dict[int, int] = {}  # canvas item → media index
            self.status = tk.StringVar(value="Photos")

            if show_chrome:
                ttk.Label(self.frame, textvariable=self.status, wraplength=720).pack(
                    anchor=tk.W, pady=(0, 4)
                )

            body = ttk.Frame(self.frame)
            body.pack(fill=tk.BOTH, expand=True)

            # Thumbnail strip — visual browse, not an engineering log.
            left = ttk.Frame(body, width=self._THUMB_COLS * (self._THUMB_CELL + self._THUMB_PAD) + 18)
            left.pack(side=tk.LEFT, fill=tk.Y)
            left.pack_propagate(False)
            self._thumb_canvas = tk.Canvas(
                left,
                width=self._THUMB_COLS * (self._THUMB_CELL + self._THUMB_PAD) + 4,
                background=BG_SUBTLE,
                highlightthickness=0,
            )
            self._thumb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            thumb_sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self._thumb_canvas.yview)
            thumb_sb.pack(side=tk.LEFT, fill=tk.Y)
            self._thumb_canvas.configure(yscrollcommand=thumb_sb.set)
            self._thumb_canvas.bind("<Button-1>", self._on_thumb_click)
            self._thumb_canvas.bind(
                "<MouseWheel>",
                lambda e: self._thumb_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )

            # Keep a hidden listbox for tests / fallback index tracking.
            self._listbox = tk.Listbox(left, width=1, exportselection=False, height=1)
            # Not packed — index mirror only.

            preview_wrap = ttk.Frame(body)
            preview_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
            self._tip_var = tk.StringVar(
                value="Explore this photo — move over a person, or drag around anything you're curious about."
            )
            self._tip = ttk.Label(
                preview_wrap,
                textvariable=self._tip_var,
                font=CAPTION,
                foreground=INK_SECONDARY,
                wraplength=640,
            )
            self._tip.pack(anchor=tk.W, pady=(0, 4))

            self.preview = tk.Canvas(preview_wrap, background=BG_DARK, highlightthickness=0)
            self.preview.pack(fill=tk.BOTH, expand=True)
            self._ink_on_dark = INK_ON_DARK
            self._caption_font = CAPTION
            self._accent = ACCENT
            self._bg_subtle = BG_SUBTLE

            self.preview.bind("<Motion>", self._on_motion)
            self.preview.bind("<Leave>", self._on_leave)
            self.preview.bind("<ButtonPress-1>", self._on_press)
            self.preview.bind("<B1-Motion>", self._on_drag)
            self.preview.bind("<ButtonRelease-1>", self._on_release)
            # Escape is bound on the toplevel when available.
            try:
                top = self.frame.winfo_toplevel()
                top.bind("<Escape>", self._on_escape, add="+")
            except tk.TclError:
                pass

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

        def set_advanced(self, advanced: bool) -> None:
            self._advanced = bool(advanced)
            if self._current_media is not None:
                self._emit_inspector()

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
                self._clear_thumbs()
                self.preview.delete("all")
                self.status.set("No photos yet — add a photo folder from Home.")
                self._call_on_select(None, soft_lines_empty=True)
                return
            board = load_canvas(path, run_id)
            media = list(board.get("media") or [])
            if self._source_types is not None:
                media = [m for m in media if (m.get("source_type") or "") in self._source_types]
            self.set_board(board, media)

        def _call_on_select(self, media_id, lines=None, selected=None, *, soft_lines_empty: bool = False):
            if self._on_select is None:
                return
            if soft_lines_empty:
                from semblon.product_surface import soft_inspector_for_media

                lines = soft_inspector_for_media({}, None)
            try:
                self._on_select(media_id, lines, selected)
            except TypeError:
                # Older 2-arg callbacks (tests / stubs).
                self._on_select(media_id, lines)

        def _clear_thumbs(self) -> None:
            self._thumb_canvas.delete("all")
            self._thumb_photos = []
            self._thumb_hitmap = {}

        def _rebuild_thumbs(self) -> None:
            """Visual photo strip — thumbnails, not path/UUID log rows."""
            from semblon.product_surface import basename_path

            self._clear_thumbs()
            cell = self._THUMB_CELL
            pad = self._THUMB_PAD
            cols = self._THUMB_COLS
            for idx, m in enumerate(self._media):
                row, col = divmod(idx, cols)
                x0 = pad + col * (cell + pad)
                y0 = pad + row * (cell + pad + 18)
                thumb = _ppm_thumb(m.get("path"), max_side=cell - 8)
                item_ids = []
                if thumb is not None:
                    data, nw, nh = thumb
                    try:
                        photo = tk.PhotoImage(data=data)
                    except tk.TclError:
                        photo = None
                    if photo is not None:
                        self._thumb_photos.append(photo)
                        ox = x0 + (cell - nw) // 2
                        oy = y0 + (cell - nh) // 2
                        iid = self._thumb_canvas.create_image(ox, oy, anchor=tk.NW, image=photo)
                        item_ids.append(iid)
                if not item_ids:
                    iid = self._thumb_canvas.create_rectangle(
                        x0,
                        y0,
                        x0 + cell,
                        y0 + cell,
                        outline="#C9C4BA",
                        fill="#EEEBE4",
                    )
                    item_ids.append(iid)
                    tid = self._thumb_canvas.create_text(
                        x0 + cell // 2,
                        y0 + cell // 2,
                        text="·",
                        fill="#8A847A",
                    )
                    item_ids.append(tid)
                label = basename_path(m.get("path"))
                if len(label) > 14:
                    label = label[:12] + "…"
                tid = self._thumb_canvas.create_text(
                    x0 + cell // 2,
                    y0 + cell + 2,
                    text=label,
                    anchor=tk.N,
                    fill="#5C574F",
                    font=("Segoe UI", 8),
                )
                item_ids.append(tid)
                for iid in item_ids:
                    self._thumb_hitmap[iid] = idx
            rows = (len(self._media) + cols - 1) // cols if self._media else 0
            height = pad + rows * (cell + pad + 18) + pad
            width = pad + cols * (cell + pad)
            self._thumb_canvas.configure(scrollregion=(0, 0, width, height))

        def _on_thumb_click(self, event) -> None:
            items = self._thumb_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for iid in items:
                idx = self._thumb_hitmap.get(iid)
                if idx is not None:
                    self.show_index(idx)
                    return

        def set_board(self, board: dict, media_rows: list[dict] | None = None) -> None:
            from semblon.product_surface import soft_canvas_status, soft_media_list_label
            from semblon.state_triple import library_include_media

            self.board = board
            self._media = list(media_rows if media_rows is not None else board.get("media") or [])
            self._listbox.delete(0, tk.END)
            face_by: dict[str, int] = {}
            for f in board.get("faces") or []:
                face_by[f["media_id"]] = face_by.get(f["media_id"], 0) + 1
            named_people = {
                f.get("person_id")
                for f in (board.get("faces") or [])
                if f.get("person_id")
            }
            unknown_faces = sum(1 for f in (board.get("faces") or []) if not f.get("person_id"))
            triples = media_state_triples(board, self._media)
            kept: list[dict] = []
            for m in self._media:
                mid = m["media_id"]
                triple = triples.get(mid)
                if triple is not None and not library_include_media(triple):
                    continue
                kept.append(m)
                nface = face_by.get(mid, 0)
                self._listbox.insert(
                    tk.END, soft_media_list_label(m, face_count=nface)
                )
            self._media = kept
            self.status.set(
                soft_canvas_status(
                    photo_count=len(self._media),
                    face_count=len(board.get("faces") or []),
                    named_people=len(named_people),
                    unknown_faces=unknown_faces,
                )
            )
            self._rebuild_thumbs()
            if self._media:
                self._listbox.selection_set(0)
                self.show_index(0)
            else:
                self.preview.delete("all")
                self._emit_inspector(media_id=None)

        def show_index(self, index: int) -> None:
            if index < 0 or index >= len(self._media):
                return
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(index)
            self.show_media(self._media[index])

        def show_media(self, media: dict) -> None:
            """Show a clean photograph. Overlays only appear on hover/select/drag."""
            if self.board is None:
                return
            self._current_media = media
            self._selected = None
            self._hover_id = None
            self._hit_regions = []
            mid = media.get("media_id")
            path = media.get("path")

            self.preview.delete("all")
            self._photo = None
            try:
                import cv2
            except ImportError as e:
                self.preview.create_text(
                    12,
                    12,
                    anchor=tk.NW,
                    fill=getattr(self, "_ink_on_dark", "#B5B1A8"),
                    text="Photo preview needs OpenCV on this machine.",
                )
                self.status.set("Preview unavailable")
                self._emit_inspector(media_id=mid)
                return

            img = cv2.imread(str(path)) if path else None
            if img is None:
                from semblon.product_surface import basename_path

                self.preview.create_text(
                    12,
                    12,
                    anchor=tk.NW,
                    fill=getattr(self, "_ink_on_dark", "#B5B1A8"),
                    text=f"Photo file missing\n{basename_path(path)}",
                )
                self._emit_inspector(media_id=mid)
                return
            try:
                data, scale, nw, nh = _ppm_photo(img)
                photo = tk.PhotoImage(data=data)
            except Exception:  # noqa: BLE001
                from semblon.product_surface import basename_path

                self.preview.create_text(
                    12,
                    12,
                    anchor=tk.NW,
                    fill=getattr(self, "_ink_on_dark", "#B5B1A8"),
                    text=f"Couldn't show this photo\n{basename_path(path)}",
                )
                self._emit_inspector(media_id=mid)
                return
            self._photo = photo
            self._scale = float(scale)
            self._nw, self._nh = nw, nh
            self.preview.create_image(0, 0, anchor=tk.NW, image=photo, tags=("photo",))
            self.preview.config(scrollregion=(0, 0, nw, nh))
            self._build_hit_regions(mid)
            self._emit_inspector(media_id=mid)

        def _build_hit_regions(self, media_id: str | None) -> None:
            from semblon.product_surface import display_rect_for_bbox, soft_object_label, soft_person_label

            self._hit_regions = []
            if not self.board or not media_id:
                return
            for f in self.board.get("faces") or []:
                if f.get("media_id") != media_id:
                    continue
                rect = display_rect_for_bbox(
                    [f.get("bbox_x1"), f.get("bbox_y1"), f.get("bbox_x2"), f.get("bbox_y2")],
                    scale=self._scale,
                )
                if rect is None:
                    continue
                self._hit_regions.append(
                    {
                        "kind": "face",
                        "id": f.get("face_id"),
                        "face": f,
                        "rect": rect,
                        "label": soft_person_label(f, board=self.board),
                    }
                )
            for it in self.board.get("items") or []:
                if it.get("media_id") != media_id or it.get("kind") == "face":
                    continue
                rect = display_rect_for_bbox(
                    [it.get("bbox_x1"), it.get("bbox_y1"), it.get("bbox_x2"), it.get("bbox_y2")],
                    scale=self._scale,
                )
                if rect is None:
                    continue
                self._hit_regions.append(
                    {
                        "kind": it.get("kind") or "object",
                        "id": it.get("item_id"),
                        "item": it,
                        "rect": rect,
                        "label": soft_object_label(it),
                    }
                )

        def _hit_at(self, x: float, y: float) -> dict | None:
            # Prefer faces; smallest containing box wins when nested.
            candidates = []
            for h in self._hit_regions:
                x1, y1, x2, y2 = h["rect"]
                if x1 <= x <= x2 and y1 <= y <= y2:
                    area = max(1.0, (x2 - x1) * (y2 - y1))
                    pri = 0 if h["kind"] == "face" else 1
                    candidates.append((pri, area, h))
            if not candidates:
                return None
            candidates.sort(key=lambda t: (t[0], t[1]))
            return candidates[0][2]

        def _clear_overlay_tags(self) -> None:
            self.preview.delete("overlay")
            self.preview.delete("drag")

        def _draw_outline(self, hit: dict, *, color: str, width: int = 2) -> None:
            x1, y1, x2, y2 = hit["rect"]
            self.preview.create_rectangle(
                x1, y1, x2, y2, outline=color, width=width, tags=("overlay",)
            )

        def _paint_interaction(self) -> None:
            self._clear_overlay_tags()
            if self._selected is not None:
                self._draw_outline(self._selected, color=self._SELECT_COLOR, width=3)
            elif self._hover_id is not None:
                hit = next((h for h in self._hit_regions if h["id"] == self._hover_id), None)
                if hit is not None:
                    self._draw_outline(hit, color=self._HOVER_COLOR, width=2)

        def _dismiss_tip(self) -> None:
            if self._tip_shown:
                self._tip_shown = False
                self._tip_var.set("")
                try:
                    self._tip.pack_forget()
                except tk.TclError:
                    pass

        def _emit_inspector(self, media_id: str | None = None) -> None:
            if self._on_select is None:
                return
            from semblon.product_surface import (
                advanced_inspector_for_media,
                soft_inspector_for_face,
                soft_inspector_for_item,
                soft_inspector_for_media,
            )

            mid = media_id
            if mid is None and self._current_media is not None:
                mid = self._current_media.get("media_id")
            board = self.board or {}

            if self._advanced:
                lines = advanced_inspector_for_media(board, mid)
                self._call_on_select(mid, lines, None)
                return

            if self._selected is not None:
                if self._selected.get("kind") == "face":
                    lines = soft_inspector_for_face(self._selected["face"], board)
                else:
                    lines = soft_inspector_for_item(self._selected.get("item") or {})
                self._call_on_select(mid, lines, self._selected)
                return

            self._call_on_select(mid, soft_inspector_for_media(board, mid), None)

        def _on_list_select(self, _evt=None) -> None:
            sel = self._listbox.curselection()
            if sel:
                self.show_index(int(sel[0]))

        def _on_motion(self, event) -> None:
            if self._drag_active or self._selected is not None:
                return
            hit = self._hit_at(event.x, event.y)
            new_id = hit["id"] if hit else None
            if new_id == self._hover_id:
                return
            self._hover_id = new_id
            self._paint_interaction()

        def _on_leave(self, _event=None) -> None:
            if self._drag_active:
                return
            self._hover_id = None
            if self._selected is None:
                self._paint_interaction()

        def _on_press(self, event) -> None:
            self._drag_origin = (event.x, event.y)
            self._drag_active = False

        def _on_drag(self, event) -> None:
            if self._drag_origin is None:
                return
            ox, oy = self._drag_origin
            if abs(event.x - ox) + abs(event.y - oy) >= self._DRAG_THRESHOLD:
                self._drag_active = True
                self._dismiss_tip()
            if not self._drag_active:
                return
            self.preview.delete("drag")
            self.preview.create_rectangle(
                ox,
                oy,
                event.x,
                event.y,
                outline=self._DRAG_COLOR,
                width=2,
                dash=(4, 3),
                tags=("drag",),
            )

        def _on_release(self, event) -> None:
            from semblon.product_surface import region_hits, soft_inspector_for_region

            origin = self._drag_origin
            self._drag_origin = None
            self.preview.delete("drag")
            if origin is None:
                return
            ox, oy = origin
            if self._drag_active:
                self._drag_active = False
                self._selected = None
                self._hover_id = None
                self._paint_interaction()
                if self.board is None or self._current_media is None:
                    return
                mid = self._current_media.get("media_id")
                # Convert display coords → image coords.
                ix1, iy1 = ox / self._scale, oy / self._scale
                ix2, iy2 = event.x / self._scale, event.y / self._scale
                hits_raw = region_hits(
                    self.board, mid, x1=ix1, y1=iy1, x2=ix2, y2=iy2
                )
                # Map to soft hits for inspector.
                soft_hits = []
                for h in hits_raw:
                    soft_hits.append(
                        {
                            "kind": h["kind"],
                            "id": h["id"],
                            "person_label": h.get("person_label"),
                            "label": h.get("label"),
                        }
                    )
                lines = soft_inspector_for_region(soft_hits, empty=not soft_hits)
                # Outline all hits in the region.
                self._clear_overlay_tags()
                id_set = {h["id"] for h in hits_raw}
                for reg in self._hit_regions:
                    if reg["id"] in id_set:
                        self._draw_outline(reg, color=self._SELECT_COLOR, width=2)
                if self._on_select is not None:
                    self._call_on_select(mid, lines, {"kind": "region", "hits": hits_raw})
                return

            # Click (not drag).
            self._drag_active = False
            hit = self._hit_at(event.x, event.y)
            if hit is None:
                self._selected = None
                self._hover_id = None
                self._paint_interaction()
                self._emit_inspector()
                return
            self._dismiss_tip()
            self._selected = hit
            self._hover_id = None
            self._paint_interaction()
            self._emit_inspector()

        def _on_escape(self, _event=None):
            self._selected = None
            self._hover_id = None
            self._drag_active = False
            self._drag_origin = None
            self.preview.delete("drag")
            self._paint_interaction()
            self._emit_inspector()
            return "break"


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

    from semblon.ui_theme import apply_theme

    apply_theme(root)
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
