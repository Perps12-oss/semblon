"""Intelligence Canvas data + tk window. Consumes observations; does not own identity."""

from __future__ import annotations

import json
from pathlib import Path

from semblon.process import default_store_path, latest_run_id
from semblon.store import connect, init_db


class CanvasError(ValueError):
    pass


def load_canvas(store: Path, run_id: str | None = None) -> dict:
    """Overlay payload: media + face boxes + non-identity items. Cluster ≠ person."""
    store = Path(store)
    if not store.is_file():
        raise CanvasError(f"store not found: {store}")
    conn = connect(store)
    init_db(conn)
    rid = run_id or latest_run_id(store, with_faces=True) or latest_run_id(store)
    if rid is None:
        conn.close()
        raise CanvasError("store has no runs")
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
    items = []
    try:
        items = conn.execute(
            """SELECT i.item_id, i.kind, i.provider, i.bbox_x1, i.bbox_y1, i.bbox_x2, i.bbox_y2,
                      i.score, i.payload_json, o.media_id
               FROM observation_items i JOIN observations o ON o.observation_id=i.observation_id
               WHERE i.run_id=?""",
            (rid,),
        ).fetchall()
    except Exception:
        items = []
    tracks = []
    try:
        tracks = conn.execute(
            "SELECT track_id, media_id, kind, t_ms_start, t_ms_end, item_count FROM tracks WHERE run_id=?",
            (rid,),
        ).fetchall()
    except Exception:
        tracks = []
    conn.close()
    return {
        "run_id": rid,
        "media": [dict(r) for r in media],
        "faces": [dict(r) for r in faces],
        "items": [
            {**dict(r), "payload": json.loads(r["payload_json"] or "{}")}
            for r in items
        ],
        "tracks": [dict(r) for r in tracks],
        "note": "Canvas overlays observations. Face identity stays FaceKit. Track ≠ person.",
    }


def run_canvas(store: Path | None = None, run_id: str | None = None) -> int:
    import tkinter as tk
    from tkinter import ttk

    board = load_canvas(store or default_store_path(), run_id)
    root = tk.Tk()
    root.title(f"Semblon Canvas — {board['run_id']}")
    root.geometry("720x480")
    ttk.Label(root, text=board["note"], wraplength=680).pack(anchor=tk.W, padx=8, pady=6)
    lb = tk.Listbox(root, height=18)
    lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    for m in board["media"]:
        nface = sum(1 for f in board["faces"] if f["media_id"] == m["media_id"])
        nitem = sum(1 for it in board["items"] if it["media_id"] == m["media_id"])
        lb.insert(tk.END, f"{m['source_type']}  faces={nface} items={nitem}  {m['path']}")
    ttk.Label(
        root,
        text=f"media={len(board['media'])} faces={len(board['faces'])} items={len(board['items'])} tracks={len(board['tracks'])}",
    ).pack(anchor=tk.W, padx=8, pady=4)
    ttk.Button(root, text="Close", command=root.destroy).pack(pady=6)
    root.mainloop()
    return 0
