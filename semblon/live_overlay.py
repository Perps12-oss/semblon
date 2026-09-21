"""Experimental live multi-person overlay scaffold (Tk).

Calls into ``live_capture`` and draws bbox + track id + ACCEPT/UNKNOWN.
Does **not** write ``faces.person_id``. Not launched from Home unless gated.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from semblon.live import LiveError, live_capture

ENV_LIVE_OVERLAY = "SEMBLON_LIVE_OVERLAY"

# Human must verify real webcam/RTSP with 2 people before Home wiring.
HUMAN_VERIFY_NOTE = (
    "Live overlay scaffold only. Human must verify real webcam/RTSP with two "
    "simultaneous people (stable track ids + ACCEPT/UNKNOWN labels) before "
    "wiring into Home. Gate: SEMBLON_LIVE_OVERLAY=1, --live-overlay, or "
    "`semblon lab live-overlay`. Overlay never assigns faces.person_id."
)


class LiveOverlayError(ValueError):
    pass


def env_overlay_enabled() -> bool:
    raw = os.environ.get(ENV_LIVE_OVERLAY, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def overlay_launch_allowed(
    *,
    explicit_flag: bool = False,
    from_home: bool = False,
) -> bool:
    """Home stays off unless env or explicit flag. Lab passes explicit_flag=True."""
    if explicit_flag or env_overlay_enabled():
        return True
    if from_home:
        return False
    return False


def format_overlay_label(ann: dict) -> str:
    track = str(ann.get("track_id") or "?")
    decision = ann.get("decision")
    if decision == "ACCEPT":
        name = ann.get("display_name") or "ACCEPT"
        if name == "ACCEPT":
            return f"{track} ACCEPT"
        return f"{track} ACCEPT {name}"
    if decision == "UNKNOWN":
        return f"{track} UNKNOWN"
    return track


def draw_overlay_bgr(frame, annotations: list[dict]):
    """Return a copy of ``frame`` with boxes + labels drawn (OpenCV)."""
    import cv2

    out = frame.copy()
    for ann in annotations or []:
        bbox = ann.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = [int(round(float(v))) for v in bbox[:4]]
        decision = ann.get("decision")
        if decision == "ACCEPT":
            color = (46, 139, 87)  # sea green BGR
        elif decision == "UNKNOWN":
            color = (60, 60, 200)
        else:
            color = (180, 180, 180)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = format_overlay_label(ann)
        ty = max(12, y1 - 6)
        cv2.putText(
            out,
            label,
            (x1, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return out


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
    return buf.tobytes(), nw, nh


def run_live_overlay(
    store: Path,
    *,
    source: str | int = 0,
    seconds: float = 5.0,
    sample_hz: float = 1.0,
    reembed_s: float = 2.0,
    retain_s: float | None = None,
    strict: bool = False,
    prefer_gpu: bool = False,
    show: bool = True,
    explicit_flag: bool = False,
    from_home: bool = False,
    capture_factory=None,
    on_overlay: Callable | None = None,
    cancel=None,
) -> dict:
    """Run live pipeline and optionally show a Tk overlay window.

    Never writes ``faces.person_id``. ``show=False`` is for tests / headless.
    """
    if not overlay_launch_allowed(explicit_flag=explicit_flag, from_home=from_home):
        raise LiveOverlayError(
            "live overlay is gated: set SEMBLON_LIVE_OVERLAY=1, pass "
            "--live-overlay / explicit_flag, or use `semblon lab live-overlay`"
        )

    store = Path(store)
    ui = {"root": None, "label": None, "photo": None, "status": None, "closed": False}

    def _close() -> None:
        ui["closed"] = True
        root = ui.get("root")
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
            ui["root"] = None

    if show:
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception as e:  # noqa: BLE001
            raise LiveOverlayError(f"tkinter required for live overlay: {e}") from e

        root = tk.Tk()
        root.title("Semblon Live Overlay (experimental)")
        root.geometry("960x640")
        ttk.Label(root, text=HUMAN_VERIFY_NOTE, wraplength=920).pack(anchor=tk.W, padx=8, pady=6)
        preview = tk.Label(root)
        preview.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        status = tk.StringVar(value="starting…")
        ttk.Label(root, textvariable=status, wraplength=920).pack(anchor=tk.W, padx=8, pady=4)
        ttk.Button(root, text="Close", command=_close).pack(pady=6)
        root.protocol("WM_DELETE_WINDOW", _close)
        ui["root"] = root
        ui["label"] = preview
        ui["status"] = status
        root.update_idletasks()
        root.update()

    def _should_cancel() -> bool:
        if ui["closed"]:
            return True
        if cancel is None:
            return False
        try:
            return bool(cancel())
        except Exception:
            return False

    def on_frame(frame, annotations) -> None:
        if on_overlay is not None:
            on_overlay(frame, annotations)
        if not show or ui["root"] is None or ui["closed"]:
            return
        try:
            drawn = draw_overlay_bgr(frame, annotations)
            data, _nw, _nh = _ppm_photo(drawn)
            import tkinter as tk

            photo = tk.PhotoImage(data=data)
            ui["photo"] = photo
            ui["label"].configure(image=photo)
            n_accept = sum(1 for a in annotations if a.get("decision") == "ACCEPT")
            n_unknown = sum(1 for a in annotations if a.get("decision") == "UNKNOWN")
            ui["status"].set(
                f"tracks={len(annotations)} accept={n_accept} unknown={n_unknown}  "
                "(overlay never assigns person_id)"
            )
            ui["root"].update_idletasks()
            ui["root"].update()
        except Exception:
            # Preview is best-effort; pipeline continues.
            pass

    try:
        rec = live_capture(
            store,
            source=source,
            seconds=seconds,
            sample_hz=sample_hz,
            reembed_s=reembed_s,
            retain_s=retain_s,
            strict=strict,
            prefer_gpu=prefer_gpu,
            capture_factory=capture_factory,
            cancel=_should_cancel,
            on_frame=on_frame,
        )
    except LiveError:
        _close()
        raise
    finally:
        if show and ui["root"] is not None and not ui["closed"]:
            # Brief idle so the last frame is visible when seconds is tiny.
            try:
                ui["root"].after(50, _close)
                ui["root"].mainloop()
            except Exception:
                _close()
        elif show:
            _close()

    return rec
