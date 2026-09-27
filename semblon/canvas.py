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


def load_bgr(path: str | None):
    """Still for the grid and the opened photo. None if the file is gone."""
    if not path:
        return None
    from semblon.temporal import read_bgr

    try:
        return read_bgr(path, None)
    except Exception:  # noqa: BLE001 — a bad file is a missing photo, not a crash
        return None


def _png_photo(img_bgr, max_side: int = 720, *, upscale: bool = False):
    """PNG that Tk PhotoImage can show. PPM data= leaves a blank tile."""
    import base64

    import cv2

    height, width = img_bgr.shape[:2]
    scale = float(max_side) / float(max(height, width, 1))
    if not upscale:
        scale = min(1.0, scale)
    nw = max(1, int(round(width * scale)))
    nh = max(1, int(round(height * scale)))
    if (nw, nh) != (width, height):
        img_bgr = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise ValueError("png encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii"), scale, nw, nh


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
        _HOVER_COLOR = "#285ECA"
        _SELECT_COLOR = "#2E6BE6"
        _DRAG_COLOR = "#E2EAFC"
        _THUMB_CELL = 156
        _THUMB_PAD = 8

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
            on_image_open=None,
        ):
            from semblon.ui_tokens import (
                ACCENT,
                ACCENT_HOVER,
                ACCENT_SUBTLE,
                BG_DARK,
                BG_SUBTLE,
                CAPTION,
                INK_ON_DARK,
                INK_SECONDARY,
            )

            self.frame = ttk.Frame(master)
            self._on_select = on_select
            self._on_image_open = on_image_open
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
            self._thumb_job = 0
            self._open = False
            self._img = None
            self._store_path: Path | None = None
            self._run_id: str | None = None
            self._ox = 0.0
            self._oy = 0.0
            self._fit_size: tuple[int, int] | None = None
            self.status = tk.StringVar(value="Photos")

            if show_chrome:
                ttk.Label(self.frame, textvariable=self.status, wraplength=720).pack(
                    anchor=tk.W, pady=(0, 4)
                )

            body = ttk.Frame(self.frame)
            body.pack(fill=tk.BOTH, expand=True)
            self._body = body

            tools = ttk.Frame(body)
            self._tools = tools
            self._back = ttk.Button(tools, text="All photos", command=self._enter_grid)

            # The grid fills the stage. A click opens that one photo.
            self._browse = ttk.Frame(body)
            self._thumb_canvas = tk.Canvas(
                self._browse,
                background=BG_SUBTLE,
                highlightthickness=0,
            )
            self._thumb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            thumb_sb = ttk.Scrollbar(self._browse, orient=tk.VERTICAL, command=self._thumb_canvas.yview)
            thumb_sb.pack(side=tk.LEFT, fill=tk.Y)
            self._thumb_canvas.configure(yscrollcommand=thumb_sb.set)
            self._thumb_canvas.bind("<Button-1>", self._on_thumb_click)
            self._thumb_canvas.bind("<Configure>", self._on_thumb_configure)
            self._thumb_canvas.bind(
                "<MouseWheel>",
                lambda e: self._thumb_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )

            # Keep a hidden listbox for tests / fallback index tracking.
            self._listbox = tk.Listbox(self.frame, width=1, exportselection=False, height=1)

            self._preview_wrap = ttk.Frame(body)
            self._tip_var = tk.StringVar(
                value="Explore this photo — move over a person, or drag around anything you're curious about."
            )
            self._tip = ttk.Label(
                self._preview_wrap,
                textvariable=self._tip_var,
                font=CAPTION,
                foreground=INK_SECONDARY,
                wraplength=640,
            )
            self._tip.pack(anchor=tk.W, pady=(0, 4))

            self.preview = tk.Canvas(self._preview_wrap, background=BG_DARK, highlightthickness=0)
            self.preview.pack(fill=tk.BOTH, expand=True)
            self._ink_on_dark = INK_ON_DARK
            self._caption_font = CAPTION
            self._accent = ACCENT
            self._bg_subtle = BG_SUBTLE
            self._SELECT_COLOR = ACCENT
            self._HOVER_COLOR = ACCENT_HOVER
            self._DRAG_COLOR = ACCENT_SUBTLE

            self.preview.bind("<Configure>", self._on_preview_configure)
            self.preview.bind("<Motion>", self._on_motion)
            self.preview.bind("<Leave>", self._on_leave)
            self.preview.bind("<ButtonPress-1>", self._on_press)
            self.preview.bind("<B1-Motion>", self._on_drag)
            self.preview.bind("<ButtonRelease-1>", self._on_release)
            self._enter_grid()
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

        def _enter_grid(self) -> None:
            """Photos fill the stage. The opened picture is not sitting beside a rail."""
            self._open = False
            self._img = None
            try:
                self._preview_wrap.pack_forget()
                self._tools.pack_forget()
            except tk.TclError:
                pass
            self._browse.pack(fill=tk.BOTH, expand=True)
            self._rebuild_thumbs()

        def _enter_open(self) -> None:
            self._open = True
            try:
                self._browse.pack_forget()
            except tk.TclError:
                pass
            self._tools.pack(fill=tk.X, pady=(0, 4))
            self._back.pack(side=tk.LEFT)
            self._preview_wrap.pack(fill=tk.BOTH, expand=True)

        def _thumb_cols(self) -> int:
            width = 0
            try:
                width = int(self._thumb_canvas.winfo_width())
            except tk.TclError:
                width = 0
            cell = self._THUMB_CELL + self._THUMB_PAD
            if width < cell * 2:
                return 4
            return max(2, width // cell)

        def _on_thumb_configure(self, event) -> None:
            if self._open or event.width < 40:
                return
            cols = max(2, event.width // (self._THUMB_CELL + self._THUMB_PAD))
            if cols != getattr(self, "_laid_cols", None):
                self._laid_cols = cols
                self._rebuild_thumbs()

        def _on_preview_configure(self, event) -> None:
            if not self._open or self._img is None:
                return
            size = (int(event.width), int(event.height))
            if size[0] < 20 or size == getattr(self, "_fit_size", None):
                return
            self._fit_size = size
            self._paint_fitted()

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
            self._store_path = path if path is not None and path.is_file() else self._store_path
            if run_id is not None:
                self._run_id = run_id
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
            """Photo grid across the stage. Tiles fill in; a click opens one."""
            from semblon.product_surface import basename_path

            self._clear_thumbs()
            self._thumb_job += 1
            job = self._thumb_job
            cell = self._THUMB_CELL
            pad = self._THUMB_PAD
            cols = self._thumb_cols()
            self._laid_cols = cols
            self._thumb_cells: dict[int, tuple[int, int]] = {}
            for idx, m in enumerate(self._media):
                row, col = divmod(idx, cols)
                x0 = pad + col * (cell + pad)
                y0 = pad + row * (cell + pad + 18)
                self._thumb_cells[idx] = (x0, y0)
                iid = self._thumb_canvas.create_rectangle(
                    x0, y0, x0 + cell, y0 + cell, outline="#2a2d34", fill="#1c1f26"
                )
                self._thumb_hitmap[iid] = idx
                label = basename_path(m.get("path"))
                if len(label) > 18:
                    label = label[:16] + "…"
                tid = self._thumb_canvas.create_text(
                    x0 + cell // 2,
                    y0 + cell + 2,
                    text=label,
                    anchor=tk.N,
                    fill="#9b9a94",
                    font=("Segoe UI", 9),
                )
                self._thumb_hitmap[tid] = idx
            rows = (len(self._media) + cols - 1) // cols if self._media else 0
            height = pad + rows * (cell + pad + 18) + pad
            width = pad + cols * (cell + pad)
            self._thumb_canvas.configure(scrollregion=(0, 0, width, max(height, 1)))
            pending = list(range(len(self._media)))

            def pump() -> None:
                if job != self._thumb_job:
                    return
                for idx in pending[:6]:
                    self._fill_thumb(idx)
                del pending[:6]
                if pending:
                    try:
                        self.frame.after(1, pump)
                    except tk.TclError:
                        return

            if pending:
                try:
                    self.frame.after(1, pump)
                except tk.TclError:
                    pass

        def _fill_thumb(self, idx: int) -> None:
            if idx >= len(self._media):
                return
            spot = self._thumb_cells.get(idx)
            if spot is None:
                return
            img = load_bgr(self._media[idx].get("path"))
            if img is None:
                return
            try:
                b64, _scale, nw, nh = _png_photo(img, max_side=self._THUMB_CELL - 8)
                photo = tk.PhotoImage(data=b64)
            except tk.TclError:
                return
            except Exception:  # noqa: BLE001
                return
            self._thumb_photos.append(photo)
            x0, y0 = spot
            cell = self._THUMB_CELL
            ox = x0 + (cell - nw) // 2
            oy = y0 + (cell - nh) // 2
            iid = self._thumb_canvas.create_image(ox, oy, anchor=tk.NW, image=photo)
            self._thumb_hitmap[iid] = idx

        def _on_thumb_click(self, event) -> None:
            x = self._thumb_canvas.canvasx(event.x)
            y = self._thumb_canvas.canvasy(event.y)
            items = self._thumb_canvas.find_overlapping(x, y, x, y)
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
            if self._media:
                self._listbox.selection_set(0)
                self._current_media = self._media[0]
                self._enter_grid()
                self._emit_inspector(media_id=self._media[0].get("media_id"))
            else:
                self.preview.delete("all")
                self._enter_grid()
                self._emit_inspector(media_id=None)

        def show_index(self, index: int) -> None:
            if index < 0 or index >= len(self._media):
                return
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(index)
            self.show_media(self._media[index])

        def show_media(self, media: dict) -> None:
            """Open one photograph across the stage. The grid is not left beside it."""
            if self.board is None:
                return
            self._current_media = media
            self._selected = None
            self._hover_id = None
            self._hit_regions = []
            self._img = None
            self._fit_size = None
            mid = media.get("media_id")
            path = media.get("path")
            self._enter_open()
            self.preview.delete("all")
            self._photo = None
            img = load_bgr(str(path) if path else None)
            if img is None:
                from semblon.product_surface import basename_path

                self.preview.create_text(
                    24,
                    48,
                    anchor=tk.NW,
                    fill=getattr(self, "_ink_on_dark", "#B5B1A8"),
                    font=self._caption_font,
                    text=f"This photo is not in the folder anymore.\n{basename_path(path)}",
                )
                self._emit_inspector(media_id=mid)
                return
            self._img = img
            self._paint_fitted()
            self._emit_inspector(media_id=mid)
            if self._on_image_open is not None:
                try:
                    self._on_image_open(media, self._img)
                except Exception:  # noqa: BLE001 — the photograph stays up if understanding cannot start
                    pass

        def refresh_open_hits(self) -> None:
            """Reload observations for the open photo. Does not leave the photograph."""
            if not self._open or self._store_path is None or self._current_media is None:
                return
            try:
                board = load_canvas(self._store_path, self._run_id)
            except Exception:  # noqa: BLE001
                return
            self.board = board
            self._build_hit_regions(self._current_media.get("media_id"))
            self._paint_interaction()

        def _paint_fitted(self) -> None:
            if self._img is None:
                return
            width = max(int(self.preview.winfo_width() or 0), 320)
            height = max(int(self.preview.winfo_height() or 0), 240)
            self.preview.delete("all")
            try:
                b64, _native, nw, nh = _png_photo(
                    self._img,
                    max_side=min(max(width - 24, height - 24, 320), 1400),
                    upscale=True,
                )
                photo = tk.PhotoImage(data=b64)
            except Exception:  # noqa: BLE001
                from semblon.product_surface import basename_path

                self.preview.create_text(
                    24,
                    48,
                    anchor=tk.NW,
                    fill=getattr(self, "_ink_on_dark", "#B5B1A8"),
                    text=f"Couldn't show this photo\n{basename_path((self._current_media or {}).get('path'))}",
                )
                return
            self._photo = photo
            ih, iw = self._img.shape[:2]
            self._scale = nw / float(max(iw, 1))
            self._nw, self._nh = nw, nh
            self._ox = max(0, (width - nw) / 2)
            self._oy = 8.0
            self.preview.create_image(self._ox, self._oy, anchor=tk.NW, image=photo, tags=("photo",))
            self.preview.config(scrollregion=(0, 0, max(width, nw), max(height, nh + 16)))
            mid = (self._current_media or {}).get("media_id")
            self._build_hit_regions(mid)
            self._paint_interaction()

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
                x1, y1, x2, y2 = rect
                rect = (x1 + self._ox, y1 + self._oy, x2 + self._ox, y2 + self._oy)
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
                x1, y1, x2, y2 = rect
                rect = (x1 + self._ox, y1 + self._oy, x2 + self._ox, y2 + self._oy)
                payload = it.get("payload") or {}
                if it.get("provider") == "visual.region":
                    label = payload.get("selected_label") or ""
                else:
                    label = soft_object_label(it)
                self._hit_regions.append(
                    {
                        "kind": payload.get("kind") or it.get("kind") or "object",
                        "id": it.get("item_id"),
                        "item": it,
                        "rect": rect,
                        "label": label,
                        "rows": payload.get("rows") or None,
                    }
                )

        def _to_image(self, x: float, y: float) -> tuple[float, float]:
            from semblon.visual.hover import display_to_image

            return display_to_image(x, y, ox=self._ox, oy=self._oy, scale=self._scale if self._scale else 1.0)

        def _hit_at(self, x: float, y: float) -> dict | None:
            # Smallest region that actually owns the pixel. Boxes are only a reject.
            from semblon.visual.masks import point_in_rows

            ix, iy = self._to_image(x, y)
            candidates = []
            for h in self._hit_regions:
                x1, y1, x2, y2 = h["rect"]
                if not (x1 <= x <= x2 and y1 <= y <= y2):
                    continue
                rows = h.get("rows")
                if rows and not point_in_rows(rows, ix, iy):
                    continue
                area = max(1.0, (x2 - x1) * (y2 - y1))
                pri = 0 if h["kind"] in {"part", "face", "text", "mark"} else 1
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

        def _draw_highlight(self, hit: dict, *, color: str, width: int = 2) -> None:
            rows = hit.get("rows")
            if rows:
                from semblon.visual.render import display_runs

                for rx1, ry1, rx2, ry2 in display_runs(
                    rows, scale=self._scale or 1.0, ox=self._ox, oy=self._oy
                ):
                    self.preview.create_rectangle(
                        rx1, ry1, rx2, ry2, outline="", fill=color, stipple="gray25", tags=("overlay",)
                    )
            self._draw_outline(hit, color=color, width=width)
            label = (hit.get("label") or "").strip()
            if not label or hit.get("kind") == "face":
                return
            x1, y1, _x2, _y2 = hit["rect"]
            chip_w = max(36, 7 * len(label) + 12)
            top = max(2, y1 - 18)
            self.preview.create_rectangle(
                x1, top, x1 + chip_w, top + 16, outline="", fill=color, tags=("overlay",)
            )
            self.preview.create_text(
                x1 + 6, top + 8, anchor=tk.W, fill="#F7F4EE", text=label, tags=("overlay",)
            )

        def _paint_interaction(self) -> None:
            self._clear_overlay_tags()
            if self._selected is not None:
                self._draw_highlight(self._selected, color=self._SELECT_COLOR, width=3)
            elif self._hover_id is not None:
                hit = next((h for h in self._hit_regions if h["id"] == self._hover_id), None)
                if hit is not None:
                    self._draw_highlight(hit, color=self._HOVER_COLOR, width=2)

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
                ix1, iy1 = self._to_image(ox, oy)
                ix2, iy2 = self._to_image(event.x, event.y)
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
