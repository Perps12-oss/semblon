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

from semblon.desktop.copy import friendly_exception, status_text
from semblon.process import ProcessCancelled, ProcessError, default_store_path, process_folder
from semblon.progress import (
    KIND_QUEUED,
    KIND_STALLED,
    STAGE_PROCESS,
    ProgressEvent,
    format_duration,
    format_progress_line,
    make_event,
    stills_percent,
)

# Tests and callers import the status line from home_ui.
__all__ = ["HOME_OBSERVERS", "HomeApp", "format_progress_line", "run_home_ui"]
from semblon.watchdog import Watchdog

# Home ingest fills cheap non-identity items for Canvas. Face remains identity.
HOME_OBSERVERS = "face,color,object"


class StillProgressBar(tk.Canvas):
    """Determinate stills bar. Fills only when the event has a real percent."""

    TRACK = "#1c1c1c"
    FILL = "#3d8bfd"
    TEXT = "#f4f4f4"
    EDGE = "#3a3a3a"

    def __init__(self, master, width: int = 520, height: int = 28, **kw):
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bg="#121212",
            **kw,
        )
        self._percent = 0.0
        self._label = "0%"
        self.bind("<Configure>", lambda _e: self.redraw())
        self.redraw()

    def reset(self) -> None:
        self._percent = 0.0
        self._label = "0%"
        self.redraw()

    def set_from_event(self, ev: ProgressEvent) -> None:
        pct = stills_percent(ev)
        if pct is None:
            return
        bits = [f"{pct:g}%"]
        if ev.files_processed is not None and ev.files_total is not None:
            bits.append(f"{ev.files_processed}/{ev.files_total}")
        self._percent = pct
        self._label = "  ".join(bits)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w = max(int(self.winfo_width() or 520), 8)
        h = max(int(self.winfo_height() or 28), 8)
        pad = 2
        self.create_rectangle(pad, pad, w - pad, h - pad, fill=self.TRACK, outline=self.EDGE)
        inner = w - 2 * pad
        fill_w = pad + int(inner * self._percent / 100.0)
        if self._percent > 0:
            self.create_rectangle(pad, pad, max(pad + 1, fill_w), h - pad, fill=self.FILL, outline="")
        self.create_text(w / 2, h / 2, text=self._label, fill=self.TEXT, font=("Segoe UI", 10, "bold"))


def format_people_lines(rec: dict) -> list[str]:
    items = rec.get("items") or []
    if not items:
        return ["No named people yet. Open Review and Name a cluster or face."]
    return [f"{i.get('display_name') or i.get('person_id')}  ({i.get('faces', 0)} faces)" for i in items]


def format_unknown_lines(rec: dict, run_id: str) -> list[str]:
    c = rec.get("counts") or {}
    return [
        f"run={run_id}",
        f"KNOWN={c.get('KNOWN', 0)}  UNKNOWN={c.get('UNKNOWN', 0)}",
        f"REVIEW_REQUIRED={c.get('REVIEW_REQUIRED', 0)}  REJECTED={c.get('REJECTED', 0)}",
        "UNKNOWN is valid. Identify never auto-assigns a person.",
    ]


def format_search_lines(rec: dict) -> list[str]:
    kind = rec.get("kind")
    if kind == "person":
        items = rec.get("items") or []
        if not items:
            return [f"No named person matching {rec.get('query')!r}."]
        return [f"{i.get('display_name') or i.get('person_id')}  ({i.get('faces', 0)} faces)  {i.get('why','')}" for i in items]
    if kind == "similar":
        lines = [
            f"similar {rec.get('query')}  modality={rec.get('modality')}  pack={rec.get('pack_id')}",
            rec.get("note") or "Similarity is not identity.",
        ]
        for i in rec.get("items") or []:
            lines.append(f"{i.get('score'):.4f}  {i.get('kind')}  {i.get('item_id')}  {i.get('why','')}")
        if rec.get("count") == 0:
            lines.append("No same-space neighbours.")
        return lines
    return [json_fallback(rec)]


def json_fallback(rec: dict) -> str:
    import json

    return json.dumps(rec, indent=2)[:4000]


class HomeApp:
    """Small entry window. Mutations stay in review-ui / review.py."""

    def __init__(self, store: Path | None = None):
        self.store = Path(store) if store is not None else default_store_path()
        self._busy = False
        self._cancel = threading.Event()
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._last_run_id: str | None = None
        self._last_review_html: Path | None = None
        self._last_folder: Path | None = None
        self._resume_ready = False
        self._q: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Semblon")
        self.root.minsize(480, 380)
        self.root.geometry("560x460")

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
        self.btn_resume = ttk.Button(row, text="Resume", command=self._resume, state=tk.DISABLED)
        self.btn_resume.pack(side=tk.LEFT, padx=(8, 0))

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
        self.btn_canvas = ttk.Button(row2, text="Canvas", command=self._open_canvas)
        self.btn_canvas.pack(side=tk.LEFT, padx=(8, 0))

        search_row = ttk.Frame(frm)
        search_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search_row, text="Find person").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.search_var, width=24).pack(side=tk.LEFT, padx=(8, 0))
        self.btn_search = ttk.Button(search_row, text="Search", command=self._search_person)
        self.btn_search.pack(side=tk.LEFT, padx=(8, 0))

        self.status = tk.StringVar(value=f"Store: {self.store}")
        ttk.Label(frm, textvariable=self.status, wraplength=520, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X, pady=(8, 0)
        )
        self.clock = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.clock, wraplength=520, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X, pady=(2, 4)
        )
        self.bar = StillProgressBar(frm)
        self.bar.pack(fill=tk.X, pady=(0, 8))

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
        self.btn_canvas.configure(state=state)
        self.btn_search.configure(state=state)
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)
        self.btn_resume.configure(
            state=tk.DISABLED if busy or not self._resume_ready else tk.NORMAL
        )

    def _request_cancel(self) -> None:
        if not self._busy:
            return
        self._cancel.set()
        self.status.set("Cancelling…")

    def _start_process(self, path: Path, *, resume: bool) -> None:
        self._last_folder = path
        self._cancel.clear()
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._resume_ready = False
        self.bar.reset()
        self.clock.set("")
        self._set_busy(True)
        queued = make_event(STAGE_PROCESS, KIND_QUEUED, path=str(path), outcome="resumed" if resume else None)
        self.status.set(status_text(queued))
        threading.Thread(target=self._run_process, args=(path, resume), daemon=True).start()

    def _choose_folder(self) -> None:
        if self._busy:
            return
        folder = filedialog.askdirectory(title="Choose a folder of photos for Semblon")
        if not folder:
            return
        self._start_process(Path(folder), resume=False)

    def _resume(self) -> None:
        if self._busy or self._last_folder is None:
            return
        self._start_process(self._last_folder, resume=True)

    def _run_process(self, folder: Path, resume: bool = False) -> None:
        def on_event(ev: ProgressEvent) -> None:
            self._wd.note(ev)
            self._q.put(("event", ev))

        try:
            rec = process_folder(
                folder,
                store=self.store,
                open_review=False,
                progress=lambda *_: None,
                on_event=on_event,
                cancel=self._cancel.is_set,
                observers=HOME_OBSERVERS,
                resume=resume,
            )
            self._q.put(("done", rec))
        except ProcessCancelled as e:
            rid = e.run_id or ""
            self._q.put(("cancelled", rid))
        except ProcessError as e:
            self._q.put(("error", e))
        except Exception as e:  # noqa: BLE001 — surface unexpected failures in home UI
            self._q.put(("error", e))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "event":
                    self.status.set(status_text(payload))
                    self.bar.set_from_event(payload)
                    bits = []
                    if payload.clock:
                        bits.append(payload.clock)
                    elapsed = format_duration(payload.elapsed_s)
                    if elapsed:
                        bits.append(f"elapsed {elapsed}")
                    eta = format_duration(payload.eta_s)
                    if eta:
                        bits.append(f"eta {eta}")
                    self.clock.set("   ".join(bits))
                elif kind == "done":
                    self._last_run_id = payload.get("run_id")
                    out = payload.get("out")
                    self._last_review_html = Path(out) if out else None
                    self._resume_ready = False
                    self._set_busy(False)
                    rid = self._last_run_id or "?"
                    self.status.set(f"Done. run_id={rid}  Open Review to name people.")
                    self.bar.set_from_event(
                        make_event(
                            STAGE_PROCESS,
                            "completed",
                            current=1,
                            total=1,
                            files_processed=1,
                            files_total=1,
                        )
                    )
                elif kind == "cancelled":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    extra = f" run_id={payload}" if payload else ""
                    self.status.set(
                        f"Cancelled.{extra} Any partial results have been retained. Resume continues from the next unfinished stage."
                    )
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
                elif kind == "error":
                    self._resume_ready = self._last_folder is not None
                    self._set_busy(False)
                    if isinstance(payload, BaseException):
                        user, detail = friendly_exception(payload)
                        self.status.set(user.replace("\n", " "))
                        messagebox.showerror("Semblon", f"{user}\n\n{detail}" if detail else user)
                    else:
                        self.status.set(f"Couldn't finish. {payload}")
                        messagebox.showerror("Semblon", str(payload))
                    if self._exit_after_cancel and self.root.winfo_exists():
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        if self._busy:
            stalled = self._wd.check()
            if stalled is not None and stalled.kind == KIND_STALLED:
                self.status.set(status_text(stalled))
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

    def _list_window(self, title: str, lines: list[str]) -> None:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("520x360")
        lb = tk.Listbox(win)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for line in lines:
            lb.insert(tk.END, line)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

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
        self._list_window("People", format_people_lines(rec))

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
        self._list_window("Unknown / inbox", format_unknown_lines(rec, rid))

    def _show_activity(self) -> None:
        from semblon.process import empty_state_line, latest_run_id
        from semblon.store import connect, init_db, integrity_report

        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        rid = latest_run_id(self.store) or "?"
        line = empty_state_line(self.store, rid) if rid != "?" else "no runs"
        try:
            integ = integrity_report(self.store)
            extra = f"integrity ok={integ['ok']} unfinished={len(integ['unfinished_runs'])}"
        except OSError:
            extra = "integrity unavailable"
        n_groups = n_items = n_rel = 0
        try:
            conn = connect(self.store)
            init_db(conn)
            n_groups = conn.execute("SELECT COUNT(*) FROM observation_groups").fetchone()[0]
            n_items = conn.execute("SELECT COUNT(*) FROM observation_items").fetchone()[0]
            n_rel = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
            conn.close()
        except Exception:
            pass
        self._list_window(
            "Activity",
            [
                line,
                extra,
                f"observation_groups={n_groups}  items={n_items}  relationships={n_rel}",
                "groups are not people",
            ],
        )

    def _open_canvas(self) -> None:
        from semblon.canvas import CanvasError, run_canvas

        try:
            run_canvas(self.store, self._last_run_id, parent=self.root)
        except CanvasError as e:
            messagebox.showerror("Semblon", str(e))

    def _search_person(self) -> None:
        from semblon.search import SearchError, search_person

        q = (self.search_var.get() or "").strip()
        if not q:
            messagebox.showinfo("Semblon", "Type a person name first.")
            return
        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        try:
            rec = search_person(self.store, q)
        except SearchError as e:
            messagebox.showerror("Semblon", str(e))
            return
        self._list_window("Search", format_search_lines(rec))

    def _show_settings(self) -> None:
        from semblon.observers import optional_status
        from semblon.providers import weights_status

        w = weights_status()
        st = optional_status()
        self._list_window(
            "Settings",
            [
                f"Store: {self.store}",
                "Cancel: between files (not mid-file)",
                "Resume: next to Cancel; continues cancelled/interrupted run from next unfinished stage",
                "Stills bar: real files done / files total, climbs to 100%",
                "Provider: FaceKit CPU (not claimed GPU)",
                f"Home observers: {HOME_OBSERVERS}",
                f"Weights dir: {w['dir']}",
                f"onnx files: {w['onnx_count']}  bundled={w['bundled']}",
                w["note"],
                f"optional ocr={st['ocr']} clip={st['clip']} pose={st['pose']}",
                st["identity"],
            ],
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
