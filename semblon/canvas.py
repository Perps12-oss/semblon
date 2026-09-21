"""Observation overlay data + tk window.

Draws boxes/tracks from persisted observations. Not identity and not the S8 shell.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from semblon.process import default_store_path, latest_run_id


class CanvasError(ValueError):
    pass


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
    note = "Canvas overlays observations. Face identity stays FaceKit. Track ≠ person."
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
    """Display boxes for one media. Includes persisted track lane IDs when present.

    When ``live_overlay`` is ON (default after VERIFY), attaches R3 overlay
    styles via ``apply_overlay_styles``. Never assigns ``person_id``.
    """
    boxes = []
    lane_by_face = board.get("track_lane_by_face") or {}
    lane_by_item = board.get("track_lane_by_item") or {}
    for f in board.get("faces") or []:
        if f.get("media_id") != media_id:
            continue
        lane = lane_by_face.get(f.get("face_id"))
        tag = "named" if f.get("person_id") else ("group" if f.get("cluster_id") else "unassigned")
        if lane:
            tag = f"{tag} lane={lane}"
        if f.get("person_id"):
            display_state = "confirmed"
        elif f.get("cluster_id"):
            display_state = "possible"
        else:
            display_state = "unknown"
        boxes.append(
            {
                "kind": "face",
                "id": f.get("face_id"),
                "bbox": [f.get("bbox_x1"), f.get("bbox_y1"), f.get("bbox_x2"), f.get("bbox_y2")],
                "tag": tag,
                "color": "#2e8b57",
                "display_state": display_state,
            }
        )
    for it in board.get("items") or []:
        if it.get("media_id") != media_id or it.get("kind") == "face":
            continue
        if it.get("bbox_x1") is None:
            continue
        lane = lane_by_item.get(it.get("item_id"))
        tag = it.get("provider")
        if lane:
            tag = f"{tag} lane={lane}"
        boxes.append(
            {
                "kind": it.get("kind"),
                "id": it.get("item_id"),
                "bbox": [it.get("bbox_x1"), it.get("bbox_y1"), it.get("bbox_x2"), it.get("bbox_y2")],
                "tag": tag,
                "color": "#c47a1a",
                "display_state": "unknown",
            }
        )
    from semblon.overlay_preview import apply_overlay_styles

    return apply_overlay_styles(boxes)


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


def run_canvas(store: Path | None = None, run_id: str | None = None, *, parent=None) -> int:
    import tkinter as tk
    from tkinter import ttk

    import cv2

    board = load_canvas(store or default_store_path(), run_id)
    own = parent is None
    root = tk.Tk() if own else tk.Toplevel(parent)
    root.title(f"Semblon Canvas — {board['run_id']}")
    root.geometry("960x640")
    ttk.Label(root, text=board["note"], wraplength=920).pack(anchor=tk.W, padx=8, pady=6)
    body = ttk.Frame(root)
    body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    lb = tk.Listbox(body, width=42)
    lb.pack(side=tk.LEFT, fill=tk.Y)
    preview = tk.Canvas(body, background="#111", highlightthickness=0)
    preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
    status = tk.StringVar(
        value=f"media={len(board['media'])} faces={len(board['faces'])} items={len(board['items'])} tracks={len(board['tracks'])}"
    )
    ttk.Label(root, textvariable=status, wraplength=920).pack(anchor=tk.W, padx=8, pady=4)
    ttk.Button(root, text="Close", command=root.destroy).pack(pady=6)

    media = board["media"]
    for m in media:
        nface = sum(1 for f in board["faces"] if f["media_id"] == m["media_id"])
        nitem = sum(1 for it in board["items"] if it["media_id"] == m["media_id"])
        lb.insert(tk.END, f"{m['source_type']}  faces={nface} items={nitem}  {m['path']}")

    def show(index: int) -> None:
        preview.delete("all")
        root._photo = None  # noqa: SLF001 — keep PhotoImage alive
        if index < 0 or index >= len(media):
            return
        m = media[index]
        path = m["path"]
        img = cv2.imread(str(path))
        if img is None:
            preview.create_text(12, 12, anchor=tk.NW, fill="#ddd", text=f"file missing\n{path}")
            status.set(f"file missing  {path}")
            return
        try:
            data, scale, nw, nh = _ppm_photo(img)
            photo = tk.PhotoImage(data=data)
        except Exception as e:  # noqa: BLE001 — preview is optional
            preview.create_text(12, 12, anchor=tk.NW, fill="#ddd", text=f"preview unavailable: {type(e).__name__}\n{path}")
            return
        root._photo = photo
        preview.create_image(0, 0, anchor=tk.NW, image=photo)
        preview.config(scrollregion=(0, 0, nw, nh))
        boxes = overlay_boxes(board, m["media_id"])
        for box in boxes:
            x1, y1, x2, y2 = box["bbox"]
            if None in (x1, y1, x2, y2):
                continue
            style = box.get("overlay_style") or {}
            border = (style.get("border") or {}) if isinstance(style, dict) else {}
            layers = (style.get("layers") or {}) if isinstance(style, dict) else {}
            semantic = (layers.get("semantic") or {}).get("color")
            outline = semantic or box.get("color") or "#2e8b57"
            width = 3 if border.get("style") == "solid" else 2
            preview.create_rectangle(
                x1 * scale,
                y1 * scale,
                x2 * scale,
                y2 * scale,
                outline=outline,
                width=width,
            )
            label = f"{box['kind']} {box['tag']}"
            notch = (style.get("notch") or {}) if isinstance(style, dict) else {}
            mark = notch.get("mark") or border.get("mark")
            if mark:
                label = f"{label} {mark}"
            preview.create_text(
                x1 * scale + 4,
                y1 * scale + 4,
                anchor=tk.NW,
                fill=outline,
                text=label,
            )
        status.set(f"{path}  boxes={len(boxes)}  group ≠ person")

    def on_select(_evt=None) -> None:
        sel = lb.curselection()
        if sel:
            show(int(sel[0]))

    lb.bind("<<ListboxSelect>>", on_select)
    if media:
        lb.selection_set(0)
        show(0)
    if own:
        root.mainloop()
    return 0
