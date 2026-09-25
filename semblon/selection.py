"""Drag-to-select geometry and the Home region window. A selection is a query."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.lens import query_image
from semblon.runtime_contract import failure_disguised_as_empty


def widget_drag_to_image(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    view_w: int,
    view_h: int,
    image_w: int,
    image_h: int,
) -> dict | None:
    """Map a widget drag into image pixels. Zero-area drags are not a search."""
    if view_w <= 0 or view_h <= 0 or image_w <= 0 or image_h <= 0:
        return None
    left, right = sorted((int(x0), int(x1)))
    top, bottom = sorted((int(y0), int(y1)))
    if right <= left or bottom <= top:
        return None

    def scale_x(value: int) -> int:
        return int(round(value * image_w / view_w))

    def scale_y(value: int) -> int:
        return int(round(value * image_h / view_h))

    ix, iy = scale_x(left), scale_y(top)
    iw, ih = scale_x(right) - ix, scale_y(bottom) - iy
    if iw <= 0 or ih <= 0:
        return None
    return {"x": ix, "y": iy, "w": iw, "h": ih}


def format_query_lines(report) -> list[str]:
    lines = ["Selection"]
    region = report.region
    lines.append(
        f"{region.get('w')}×{region.get('h')} at {region.get('x')},{region.get('y')}"
    )
    for row in report.results:
        if failure_disguised_as_empty(row):
            raise RuntimeError(row.capability_id)
        if row.status == "SUCCESS":
            label = row.items[0].label if row.items else ""
            lines.append(f"{row.capability_id}: {label}")
        elif row.status == "NO_RESULT":
            lines.append(f"{row.capability_id}: ran, nothing matched")
        else:
            lines.append(row.reason or f"{row.capability_id} did not run")
    return lines


def media_file(store: Path, media_id: str | None) -> Path | None:
    if not media_id or not Path(store).is_file():
        return None
    conn = sqlite3.connect(str(store))
    try:
        row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None or not row[0]:
        return None
    path = Path(row[0])
    return path if path.is_file() else None


def open_region_window(master, image_path: Path, on_lines) -> None:
    """Tk drag rectangle. Releases into the same query pipeline as lab query."""
    import tkinter as tk

    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        on_lines(["Could not read that photo. Nothing was searched."])
        return
    image_h, image_w = image.shape[:2]
    view_w = min(800, image_w)
    view_h = max(1, int(round(image_h * (view_w / image_w))))
    shown = cv2.resize(image, (view_w, view_h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)
    win = tk.Toplevel(master)
    win.title("Select a region")
    canvas = tk.Canvas(win, width=view_w, height=view_h, highlightthickness=0)
    canvas.pack()
    ppm = f"P6\n{view_w} {view_h}\n255\n".encode() + rgb.tobytes()
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".ppm", delete=False)
    tmp.write(ppm)
    tmp.close()
    photo = tk.PhotoImage(file=tmp.name)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    canvas.image = photo
    state = {"x": 0, "y": 0, "box": None}

    def press(event):
        state["x"], state["y"] = event.x, event.y
        if state["box"] is not None:
            canvas.delete(state["box"])
        state["box"] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#c4554a")

    def drag(event):
        if state["box"] is None:
            return
        canvas.coords(state["box"], state["x"], state["y"], event.x, event.y)

    def release(event):
        rect = widget_drag_to_image(
            state["x"],
            state["y"],
            event.x,
            event.y,
            view_w=view_w,
            view_h=view_h,
            image_w=image_w,
            image_h=image_h,
        )
        if rect is None:
            on_lines(["Draw a region first. Nothing was searched."])
            return
        report = query_image(image, x=rect["x"], y=rect["y"], w=rect["w"], h=rect["h"])
        on_lines(format_query_lines(report))
        win.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
