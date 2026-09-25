"""Drag-to-select geometry and the Home Lens region flow. A selection is a query.

Lens never writes faces.person_id or embeddings.modality='face'. Inference runs
off the UI thread when a schedule callback is provided.
The user's rectangle is authoritative. Models may add a second observation.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Callable

from semblon.geometry import widget_to_image
from semblon.lens import query_image
from semblon.runtime_contract import failure_disguised_as_empty

LENS_HEADLINE = "Lens"
LENS_SUBCOPY = (
    "Ask about something in a photo. Semblon uses whatever understanding "
    "is available on this computer."
)
LENS_EMPTY_GUIDE = "Open a photo, then select something to look at."
LENS_BUSY = "Looking…"
LENS_SELECT_HINT = (
    "Drag a box on the photo. Semblon uses whatever understanding is available."
)
UNKNOWN_HEADLINE = "Unknown selection"
UNKNOWN_BODY = "We couldn't identify this yet."


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
    """Map a widget drag into image pixels. Letterboxed views keep image space true."""
    return widget_to_image(
        x0,
        y0,
        x1,
        y1,
        view_w=view_w,
        view_h=view_h,
        image_w=image_w,
        image_h=image_h,
        letterbox=True,
    )


def _capability_plain(capability_id: str) -> str:
    try:
        from semblon.runtime_contract import default_catalog

        spec = default_catalog().get(capability_id)
        return spec.label
    except Exception:  # noqa: BLE001
        return (capability_id or "Result").replace("_", " ").strip().capitalize()


def format_query_lines(report) -> list[str]:
    """Lens result lines. No embed_siglip / ground_selection names."""
    lines = ["Lens"]
    region = report.region or {}
    w, h = region.get("w"), region.get("h")
    if w and h:
        lines.append(f"Selected area · {w}×{h}")
    identified = False
    for row in report.results:
        if failure_disguised_as_empty(row):
            raise RuntimeError(row.capability_id)
        if row.capability_id == "grounding" and row.fallback == "RECTANGULAR_CROP":
            continue
        plain = _capability_plain(row.capability_id)
        if row.status == "SUCCESS":
            hit = row.items[0].label if row.items else ""
            if hit and hit.lower() not in {
                "siglip",
                "sam2",
                "ocr",
                "vlm",
                "argos",
                "tesseract",
                "watch",
            }:
                lines.append(f"{plain}: {hit}")
                identified = True
            else:
                lines.append(f"{plain}: found something")
                identified = True
        elif row.status == "NO_RESULT":
            continue
        else:
            continue
    if not identified:
        lines.append(UNKNOWN_HEADLINE)
        lines.append(UNKNOWN_BODY)
    return lines


def lens_result_summary(report) -> dict:
    results = list(getattr(report, "results", ()) or ())
    if not results:
        return {
            "status": "UNAVAILABLE",
            "reason": "Nothing was searched.",
            "item_count": 0,
        }
    success = [
        r
        for r in results
        if r.status == "SUCCESS"
        and r.items
        and not (r.capability_id == "grounding" and r.fallback == "RECTANGULAR_CROP")
    ]
    if success:
        n = sum(len(r.items) for r in success)
        return {
            "status": "SUCCESS",
            "summary": f"{n} result{'s' if n != 1 else ''}",
            "item_count": n,
            "items": [{"label": i.label} for r in success for i in r.items],
        }
    return {
        "status": "NO_RESULT",
        "reason": UNKNOWN_BODY,
        "headline": UNKNOWN_HEADLINE,
        "item_count": 0,
    }


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


def media_basename(store: Path, media_id: str | None) -> str | None:
    path = media_file(store, media_id)
    if path is None:
        return None
    return path.name


def run_lens_query(
    image_path: Path,
    *,
    x: int | None = None,
    y: int | None = None,
    w: int | None = None,
    h: int | None = None,
    schedule: Callable[[Callable[[], None]], None] | None = None,
    on_lines: Callable[[list[str]], None] | None = None,
    on_report: Callable | None = None,
    on_error: Callable[[BaseException], None] | None = None,
    on_busy: Callable[[bool], None] | None = None,
) -> None:
    def _finish_ok(report) -> None:
        if on_report is not None:
            try:
                on_report(report)
            except Exception:  # noqa: BLE001
                pass
        if on_lines is not None:
            try:
                on_lines(format_query_lines(report))
            except Exception as exc:  # noqa: BLE001
                if on_error is not None:
                    on_error(exc)
                elif on_lines is not None:
                    on_lines(["Semblon could not finish looking. Nothing was searched."])

    def _finish_err(exc: BaseException) -> None:
        if on_error is not None:
            try:
                on_error(exc)
                return
            except Exception:  # noqa: BLE001
                pass
        if on_lines is not None:
            on_lines(["Semblon could not finish looking.", "Nothing was searched."])

    def work() -> None:
        try:
            import cv2

            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                lines = ["Could not read that photo. Nothing was searched."]

                def _bad() -> None:
                    if on_busy is not None:
                        on_busy(False)
                    if on_lines is not None:
                        on_lines(lines)

                if schedule is not None:
                    schedule(_bad)
                else:
                    _bad()
                return
            report = query_image(image, x=x, y=y, w=w, h=h)

            def _ok() -> None:
                if on_busy is not None:
                    on_busy(False)
                _finish_ok(report)

            if schedule is not None:
                schedule(_ok)
            else:
                _ok()
        except Exception as exc:  # noqa: BLE001

            def _err() -> None:
                if on_busy is not None:
                    on_busy(False)
                _finish_err(exc)

            if schedule is not None:
                schedule(_err)
            else:
                _err()

    if on_busy is not None:
        on_busy(True)
    if schedule is None:
        work()
        return
    threading.Thread(target=work, name="semblon-lens-query", daemon=True).start()


def _prepare_view(image_path: Path):
    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return None
    image_h, image_w = image.shape[:2]
    view_w = min(800, image_w)
    view_h = max(1, int(round(image_h * (view_w / image_w))))
    shown = cv2.resize(image, (view_w, view_h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)
    return {
        "image": image,
        "image_w": image_w,
        "image_h": image_h,
        "view_w": view_w,
        "view_h": view_h,
        "rgb": rgb,
    }


def mount_region_select(
    parent,
    image_path: Path,
    *,
    on_lines,
    on_report=None,
    on_busy=None,
    schedule: Callable[[Callable[[], None]], None] | None = None,
    on_close: Callable[[], None] | None = None,
    hint_text: str = LENS_SELECT_HINT,
) -> object | None:
    import tempfile
    import tkinter as tk

    prepared = _prepare_view(image_path)
    if prepared is None:
        on_lines(["Could not read that photo. Nothing was searched."])
        return None

    frame = tk.Frame(parent)
    hint = tk.Label(frame, text=hint_text, anchor="w", padx=8, pady=4)
    hint.pack(fill="x")
    canvas = tk.Canvas(
        frame,
        width=prepared["view_w"],
        height=prepared["view_h"],
        highlightthickness=0,
    )
    canvas.pack()
    ppm = (
        f"P6\n{prepared['view_w']} {prepared['view_h']}\n255\n".encode()
        + prepared["rgb"].tobytes()
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".ppm", delete=False)
    tmp.write(ppm)
    tmp.close()
    photo = tk.PhotoImage(file=tmp.name)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    canvas.image = photo
    state = {"x": 0, "y": 0, "box": None, "busy": False}

    def press(event):
        if state["busy"]:
            return
        state["x"], state["y"] = event.x, event.y
        if state["box"] is not None:
            canvas.delete(state["box"])
        state["box"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#c4554a"
        )

    def drag(event):
        if state["box"] is None or state["busy"]:
            return
        canvas.coords(state["box"], state["x"], state["y"], event.x, event.y)

    def release(event):
        if state["busy"]:
            return
        rect = widget_drag_to_image(
            state["x"],
            state["y"],
            event.x,
            event.y,
            view_w=prepared["view_w"],
            view_h=prepared["view_h"],
            image_w=prepared["image_w"],
            image_h=prepared["image_h"],
        )
        if rect is None:
            on_lines(["Draw a region first. Nothing was searched."])
            return
        # Keep the same canvas rectangle. Do not replace it with a model box.

        def _busy(flag: bool) -> None:
            state["busy"] = flag
            if on_busy is not None:
                on_busy(flag)

        def _done_lines(lines: list[str]) -> None:
            on_lines(lines)
            if on_close is not None:
                on_close()

        run_lens_query(
            image_path,
            x=rect["x"],
            y=rect["y"],
            w=rect["w"],
            h=rect["h"],
            schedule=schedule,
            on_lines=_done_lines,
            on_report=on_report,
            on_busy=_busy,
        )

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    return frame


def open_region_window(
    master,
    image_path: Path,
    on_lines,
    *,
    on_report=None,
    on_busy=None,
    schedule: Callable[[Callable[[], None]], None] | None = None,
) -> None:
    import tkinter as tk

    win = tk.Toplevel(master)
    win.title("Lens — select a region")

    def _close() -> None:
        try:
            win.destroy()
        except tk.TclError:
            pass

    if schedule is None and hasattr(master, "after"):
        schedule = lambda fn: master.after(0, fn)  # noqa: E731

    mounted = mount_region_select(
        win,
        image_path,
        on_lines=on_lines,
        on_report=on_report,
        on_busy=on_busy,
        schedule=schedule,
        on_close=_close,
    )
    if mounted is None:
        _close()
        return
    mounted.pack(fill="both", expand=True)
