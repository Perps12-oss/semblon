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


def _capability_plain(capability_id: str) -> str:
    """Product verb for a capability — never provider / internal ids."""
    try:
        from semblon.runtime_contract import default_catalog

        spec = default_catalog().get(capability_id)
        return spec.label
    except Exception:  # noqa: BLE001 — soft fallback
        return (capability_id or "Result").replace("_", " ").strip().capitalize()


def format_query_lines(report) -> list[str]:
    """Lens result lines for normal UX. No embed_siglip / ground_selection names."""
    lines = ["Lens"]
    region = report.region or {}
    w, h = region.get("w"), region.get("h")
    if w and h:
        lines.append(f"Selected area · {w}×{h}")
    for row in report.results:
        if failure_disguised_as_empty(row):
            raise RuntimeError(row.capability_id)
        plain = _capability_plain(row.capability_id)
        if row.status == "SUCCESS":
            hit = row.items[0].label if row.items else ""
            # Prefer catalog/product labels; strip provider tokens from item labels.
            if hit and hit.lower() not in {
                "siglip",
                "sam2",
                "ocr",
                "vlm",
                "argos",
                "tesseract",
            }:
                lines.append(f"{plain}: {hit}")
            else:
                lines.append(f"{plain}: found something")
        elif row.status == "NO_RESULT":
            lines.append(f"{plain}: ran, nothing matched")
        else:
            lines.append(row.reason or f"{plain} did not run")
    if len(lines) == 1:
        lines.append("Nothing was searched.")
    return lines


def lens_result_summary(report) -> dict:
    """Compact last-result payload for the Home shell (honest status)."""
    results = list(getattr(report, "results", ()) or ())
    if not results:
        return {
            "status": "UNAVAILABLE",
            "reason": "Nothing was searched.",
            "item_count": 0,
        }
    success = [r for r in results if r.status == "SUCCESS" and r.items]
    if success:
        n = sum(len(r.items) for r in success)
        return {
            "status": "SUCCESS",
            "summary": f"{n} result{'s' if n != 1 else ''}",
            "item_count": n,
            "items": [{"label": i.label} for r in success for i in r.items],
        }
    no_result = [r for r in results if r.status == "NO_RESULT"]
    if no_result and all(r.status == "NO_RESULT" for r in results):
        return {
            "status": "NO_RESULT",
            "reason": "Semblon looked and found nothing in that area.",
            "item_count": 0,
        }
    failed = next(
        (r for r in results if r.status in {"UNAVAILABLE", "ERROR", "TIMEOUT", "CANCELLED"}),
        None,
    )
    if failed is not None:
        return {
            "status": failed.status,
            "reason": failed.reason or "It did not run.",
            "item_count": 0,
        }
    return {"status": "NO_RESULT", "reason": "Nothing matched.", "item_count": 0}


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


def open_region_window(master, image_path: Path, on_lines, *, on_report=None) -> None:
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
    win.title("Lens — select a region")
    hint = tk.Label(
        win,
        text="Drag a box on the photo. Semblon uses whatever understanding is available.",
        anchor="w",
        padx=8,
        pady=4,
    )
    hint.pack(fill="x")
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
        if on_report is not None:
            try:
                on_report(report)
            except Exception:  # noqa: BLE001 — UI path must still show lines
                pass
        on_lines(format_query_lines(report))
        win.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
