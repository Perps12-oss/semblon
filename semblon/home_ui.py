"""Double-click home — Choose folder / Open review. Not full S8 shell.

Opaque tkinter. No Mica. Cooperative cancel stops ingest between files.
Progress text comes from process on_event only — no invented percent.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from semblon.process import ProcessCancelled, ProcessError, default_store_path, process_folder
from semblon.progress import ProgressEvent


def format_progress_line(ev: ProgressEvent) -> str:
    """Human status line. Never invents a percent when the event has none."""
    parts = [f"{ev.stage}:{ev.kind}"]
    if ev.message:
        parts.append(ev.message)
    if ev.files_processed is not None and ev.files_total is not None:
        parts.append(f"files {ev.files_processed}/{ev.files_total}")
    elif ev.current is not None and ev.total is not None:
        parts.append(f"{ev.current}/{ev.total}")
    if ev.percent is not None:
        parts.append(f"{ev.percent:g}%")
    if ev.run_id:
        parts.append(f"run={ev.run_id}")
    if ev.error:
        parts.append(ev.error)
    return "  ".join(parts)


class HomeApp:
    """Small entry window. Mutations stay in review-ui / review.py."""

    def __init__(self, store: Path | None = None):
        self.store = Path(store) if store is not None else default_store_path()
        self._busy = False
        self._cancel = threading.Event()
        self._exit_after_cancel = False
        self._last_run_id: str | None = None
        self._last_review_html: Path | None = None
        self._q: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Semblon")
        self.root.minsize(480, 280)
        self.root.geometry("560x340")

        frm = ttk.Frame(self.root, padding=16)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="SEMBLON", font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(
            frm,
            text="Choose a photo folder to process, or open Review to name people.",
            wraplength=480,
        ).pack(anchor=tk.W, pady=(4, 4))
        ttk.Label(
            frm,
            text="Local-first. buffalo_l weights are internal evaluation only — not a commercial pack.",
            wraplength=480,
        ).pack(anchor=tk.W, pady=(0, 12))

        row = ttk.Frame(frm)
        row.pack(fill=tk.X, pady=(0, 8))
        self.btn_folder = ttk.Button(row, text="Choose folder…", command=self._choose_folder)
        self.btn_folder.pack(side=tk.LEFT)
        self.btn_review = ttk.Button(row, text="Open Review", command=self._open_review_ui)
        self.btn_review.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_html = ttk.Button(row, text="Open review.html", command=self._open_html)
        self.btn_html.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_cancel = ttk.Button(row, text="Cancel", command=self._request_cancel, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=(8, 0))

        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=(0, 8))
        self.btn_people = ttk.Button(row2, text="People", command=self._show_people)
        self.btn_people.pack(side=tk.LEFT)
        self.btn_unknown = ttk.Button(row2, text="Unknown", command=self._show_unknown)
        self.btn_unknown.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_activity = ttk.Button(row2, text="Activity", command=self._show_activity)
        self.btn_activity.pack(side=tk.LEFT, padx=(8, 0))
        self.btn_settings = ttk.Button(row2, text="Settings", command=self._show_settings)
        self.btn_settings.pack(side=tk.LEFT, padx=(8, 0))

        self.status = tk.StringVar(value=f"Store: {self.store}")
        ttk.Label(frm, textvariable=self.status, wraplength=480, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X, pady=(8, 0)
        )

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_folder.configure(state=state)
        self.btn_review.configure(state=state)
        self.btn_html.configure(state=state)
        self.btn_people.configure(state=state)
        self.btn_unknown.configure(state=state)
        self.btn_activity.configure(state=state)
        self.btn_settings.configure(state=state)
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _request_cancel(self) -> None:
        if not self._busy:
            return
        self._cancel.set()
        self.status.set("Cancelling…")

    def _choose_folder(self) -> None:
        if self._busy:
            return
        folder = filedialog.askdirectory(title="Choose a folder of photos for Semblon")
        if not folder:
            return
        path = Path(folder)
        self._cancel.clear()
        self._exit_after_cancel = False
        self._set_busy(True)
        self.status.set(f"Processing: {path}")
        threading.Thread(target=self._run_process, args=(path,), daemon=True).start()

    def _run_process(self, folder: Path) -> None:
        def on_event(ev: ProgressEvent) -> None:
            self._q.put(("status", format_progress_line(ev)))

        try:
            rec = process_folder(
                folder,
                store=self.store,
                open_review=False,
                progress=lambda *_: None,
                on_event=on_event,
                cancel=self._cancel.is_set,
            )
            self._q.put(("done", rec))
        except ProcessCancelled as e:
            rid = e.run_id or ""
            self._q.put(("cancelled", rid))
        except ProcessError as e:
            self._q.put(("error", str(e)))
        except Exception as e:  # noqa: BLE001 — surface unexpected failures in home UI
            self._q.put(("error", f"{type(e).__name__}: {e}"))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "done":
                    self._last_run_id = payload.get("run_id")
                    out = payload.get("out")
                    self._last_review_html = Path(out) if out else None
                    self._set_busy(False)
                    rid = self._last_run_id or "?"
                    self.status.set(f"Done. run_id={rid}  Open Review to name people.")
                elif kind == "cancelled":
                    self._set_busy(False)
                    extra = f" run_id={payload}" if payload else ""
                    self.status.set(
                        f"Cancelled.{extra} Partial results remain in the store. Open Review for what exists."
                    )
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
                elif kind == "error":
                    self._set_busy(False)
                    self.status.set(f"Failed: {payload}")
                    messagebox.showerror("Semblon", payload)
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._drain_queue)

    def _open_review_ui(self) -> None:
        if self._busy:
            return
        from semblon.review_ui import ReviewUiError, run_review_ui

        try:
            # Hide home while review-ui owns the event loop feel; destroy after return.
            self.root.withdraw()
            run_review_ui(store=self.store, run_id=self._last_run_id)
        except ReviewUiError as e:
            messagebox.showerror("Semblon", str(e))
        finally:
            if self.root.winfo_exists():
                self.root.deiconify()

    def _open_html(self) -> None:
        if self._busy:
            return
        path = self._last_review_html
        if path is None or not path.is_file():
            from semblon.process import default_review_out

            path = default_review_out(self.store)
        if not path.is_file():
            messagebox.showinfo("Semblon", f"No review.html yet:\n{path}")
            return
        webbrowser.open(path.resolve().as_uri())

    def _show_people(self) -> None:
        from semblon.search import SearchError, search_people

        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        try:
            rec = search_people(self.store)
        except SearchError as e:
            messagebox.showerror("Semblon", str(e))
            return
        if not rec["items"]:
            messagebox.showinfo("Semblon", "No named people yet. Open Review and Name a cluster or face.")
            return
        lines = [f"{i['display_name'] or i['person_id']}  ({i['faces']} faces)" for i in rec["items"]]
        messagebox.showinfo("People", "\n".join(lines))

    def _show_unknown(self) -> None:
        from semblon.inbox import InboxError, inbox
        from semblon.process import latest_run_id

        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        rid = latest_run_id(self.store, with_faces=True)
        if rid is None:
            messagebox.showinfo("Semblon", "Store has no runs with faces.")
            return
        try:
            rec = inbox(self.store, rid)
        except InboxError as e:
            messagebox.showerror("Semblon", str(e))
            return
        c = rec.get("counts") or {}
        messagebox.showinfo(
            "Unknown / inbox",
            (
                f"run={rid}\n"
                f"KNOWN={c.get('KNOWN', 0)}  UNKNOWN={c.get('UNKNOWN', 0)}\n"
                f"REVIEW_REQUIRED={c.get('REVIEW_REQUIRED', 0)}  REJECTED={c.get('REJECTED', 0)}\n"
                "UNKNOWN is valid. Identify never auto-assigns a person."
            ),
        )

    def _show_activity(self) -> None:
        from semblon.process import empty_state_line, latest_run_id
        from semblon.store import integrity_report

        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        rid = latest_run_id(self.store) or "?"
        line = empty_state_line(self.store, rid) if rid != "?" else "no runs"
        try:
            integ = integrity_report(self.store)
            extra = f"\nintegrity ok={integ['ok']} unfinished={len(integ['unfinished_runs'])}"
        except OSError:
            extra = ""
        messagebox.showinfo("Activity", f"{line}{extra}")

    def _show_settings(self) -> None:
        from semblon.providers import weights_status

        w = weights_status()
        messagebox.showinfo(
            "Settings",
            (
                f"Store: {self.store}\n"
                f"Cancel: between files (not mid-file)\n"
                f"Provider: FaceKit CPU (not claimed GPU)\n"
                f"Weights dir: {w['dir']}\n"
                f"onnx files: {w['onnx_count']}  bundled={w['bundled']}\n"
                f"{w['note']}"
            ),
        )

    def _on_close(self) -> None:
        if self._busy:
            if messagebox.askyesno(
                "Semblon",
                "Processing is still running. Cancel and exit?",
            ):
                self._exit_after_cancel = True
                self._request_cancel()
            return
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_home_ui(store: Path | None = None) -> int:
    HomeApp(store=store).run()
    return 0
