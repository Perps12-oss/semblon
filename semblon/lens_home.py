"""Home Lens mouse-up handler. Keeps the user rectangle."""

from __future__ import annotations

from pathlib import Path


def open_region_select(home) -> None:
    """Production region select — persist box and Find Similar into Library."""
    from semblon.selection import media_file, mount_region_select, open_region_window

    path = media_file(home.store, getattr(home, "_insp_media_id", None))
    if path is None:
        home._set_inspector(
            "Details",
            [
                "Open a photo first.",
                "Then select something to look at.",
                "Nothing was searched.",
            ],
        )
        home._set_inspector_collapsed(False)
        return

    def done(lines: list[str]) -> None:
        try:
            home._set_inspector("Details", lines or ["Nothing was searched."])
            home._set_inspector_collapsed(False)
        except Exception:  # noqa: BLE001
            pass
        summary = getattr(home, "_last_lens_result", None)
        if hasattr(home, "_apply_find_similar_result") and summary:
            try:
                home._apply_find_similar_result(summary)
            except Exception:  # noqa: BLE001
                pass

    def on_rect(rect: dict) -> None:
        from semblon.lens_release import remember_selection

        media_id = getattr(home, "_insp_media_id", None)
        if not media_id:
            done(["Open a photo first.", "Nothing was searched."])
            return
        rec = remember_selection(
            home.store,
            media_id=str(media_id),
            image_path=path,
            x=int(rect["x"]),
            y=int(rect["y"]),
            w=int(rect["w"]),
            h=int(rect["h"]),
        )
        home._last_lens_result = rec.get("summary") or {}
        home._last_lens_rect = {
            "x": int(rect["x"]),
            "y": int(rect["y"]),
            "w": int(rect["w"]),
            "h": int(rect["h"]),
            "kept": True,
        }
        done(rec.get("lines") or ["No similar images found yet."])

    def on_busy(flag: bool) -> None:
        home._lens_busy = bool(flag)
        if hasattr(home, "_lens_status"):
            from semblon.selection import LENS_BUSY

            try:
                home._lens_status.set(LENS_BUSY if flag else "")
            except Exception:  # noqa: BLE001
                pass

    schedule = lambda fn: home.root.after(0, fn)  # noqa: E731

    # Prefer selecting on the open media workspace when canvas is showing a photo.
    open_region_window(
        home.root,
        path,
        done,
        on_busy=on_busy,
        schedule=schedule,
        on_rect=on_rect,
    )


def install(home_cls):
    home_cls._open_region_select = open_region_select
    return home_cls


def run_product_home(store: Path | None = None) -> int:
    """Canonical Home launch. Installs Lens persist+find, then starts Tk."""
    from semblon.home_ui import HomeApp, run_home_ui

    install(HomeApp)
    return run_home_ui(store=store)
