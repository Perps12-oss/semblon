"""Live multi-person overlay (Tk) — WIRED after human verify 2026-09-21.

Calls into ``live_capture`` and draws bbox + track id + ACCEPT/UNKNOWN.
Does **not** write ``faces.person_id``. Home entry is explicit click only
(no auto-start webcam). Opt out: SEMBLON_LIVE_OVERLAY=0 / SEMBLON_WIRE_HOME_LIVE=0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from semblon.gates import LIVE_OVERLAY, WIRE_HOME_LIVE, enabled, require_human_note
from semblon.live import LiveError, live_capture

HUMAN_VERIFY_NOTE = require_human_note(LIVE_OVERLAY)


class LiveOverlayError(ValueError):
    pass


def env_overlay_enabled() -> bool:
    return enabled(LIVE_OVERLAY)


def home_live_enabled() -> bool:
    return enabled(WIRE_HOME_LIVE)


def overlay_launch_allowed(
    *,
    explicit_flag: bool = False,
    from_home: bool = False,
) -> bool:
    """Lab/CLI uses LIVE_OVERLAY (default ON). Home requires WIRE_HOME_LIVE."""
    if from_home:
        return home_live_enabled()
    if explicit_flag:
        return True
    return env_overlay_enabled()


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
            "live overlay disabled: set SEMBLON_LIVE_OVERLAY=1 (lab) or "
            "SEMBLON_WIRE_HOME_LIVE=1 (Home), or unset opt-out "
            f"({require_human_note(LIVE_OVERLAY if not from_home else WIRE_HOME_LIVE)})"
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

        from semblon.ui_tokens import BG_DARK

        root = tk.Tk()
        root.title("Semblon Live Overlay")
        root.geometry("960x640")
        root.configure(bg=BG_DARK)
        ttk.Label(
            root,
            text="Live overlay — boxes, track id, ACCEPT/UNKNOWN. Never assigns person_id.",
            wraplength=920,
        ).pack(anchor=tk.W, padx=8, pady=6)
        preview = tk.Label(root, bg=BG_DARK)
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
