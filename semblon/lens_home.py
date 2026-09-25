"""Home Lens mouse-up handler. Keeps the user rectangle."""

from __future__ import annotations

from pathlib import Path


def open_region_select(home) -> None:
    """Production Lens release path: persist the box and find similar photos."""
    from semblon.selection import media_file, mount_region_select, open_region_window

    path = media_file(home.store, getattr(home, "_insp_media_id", None))
    if path is None:
        home._set_inspector(
            "Lens",
            [
                "Open a photo first.",
                "Then select something to look at.",
                "Nothing was searched.",
            ],
        )
        if getattr(home, "_nav", None) == "lens":
            home._refresh_lens_workspace()
        return

    def done(lines: list[str]) -> None:
        try:
            home._set_inspector("Lens", lines or ["Nothing was searched."])
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

    if getattr(home, "_nav", None) == "lens" and hasattr(home, "_lens_stage"):
        import tkinter as tk

        for child in home._lens_stage.winfo_children():
            child.destroy()
        mounted = mount_region_select(
            home._lens_stage,
            path,
            on_lines=done,
            on_busy=on_busy,
            schedule=schedule,
            on_rect=on_rect,
        )
        if mounted is not None:
            mounted.pack(fill=tk.BOTH, expand=True)
        return

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
