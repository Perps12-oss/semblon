"""Double-click home — Choose folder / Open review. Not full S8 shell.

Opaque tkinter. No Mica. Cooperative cancel stops ingest between files.
Progress text comes from process on_event only — no invented percent.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:  # pragma: no cover - depends on host Python build
    tk = None
    filedialog = messagebox = ttk = None

from semblon.process import ProcessCancelled, ProcessError, default_store_path, process_folder
from semblon.progress import KIND_QUEUED, KIND_STALLED, STAGE_PROCESS, ProgressEvent, make_event
from semblon.watchdog import Watchdog

# Home ingest fills cheap non-identity items for Canvas. Face remains identity.
HOME_OBSERVERS = "face,color,object"


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
            score = i.get("score")
            if score is None:
                s = "n/a"
            else:
                try:
                    s = f"{float(score):.4f}"
                except (TypeError, ValueError):
                    s = "n/a"
            lines.append(f"{s}  {i.get('kind')}  {i.get('item_id')}  {i.get('why','')}")
        if rec.get("count") == 0:
            lines.append("No same-space neighbours.")
        return lines
    return [json_fallback(rec)]


def format_activity_lines(
    *,
    run_line: str,
    integrity_line: str,
    groups: list[dict],
    relationships: list[dict],
    events: list[dict],
    track_count: int,
) -> list[str]:
    lines = [run_line, integrity_line]
    if groups:
        lines.append("observation_groups:")
        for g in groups:
            lines.append(
                f"  kind={g.get('kind')} members={g.get('member_count')} status={g.get('status')} (not a person)"
            )
    else:
        lines.append("observation_groups: none")

    if relationships:
        lines.append("relationships:")
        for r in relationships:
            names = [n for n in (r.get("name_a"), r.get("name_b")) if n]
            ids = [i for i in [r.get("src_person_id"), *(r.get("other_person_ids") or [])] if i]
            who = ", ".join(names) if names else (", ".join(ids) if ids else "unknown")
            lines.append(
                f"  kind={r.get('kind')} people={who} confirmed={r.get('confirmed', 0)}"
            )
    else:
        lines.append("relationships: none")

    if events:
        lines.append("events:")
        for ev in events:
            lines.append(
                f"  {ev.get('label')}  {ev.get('t_start')} -> {ev.get('t_end')}  folder={ev.get('folder')}"
            )
    else:
        lines.append("events: none")

    lines.append(f"tracks={track_count}  (track ≠ person)")
    return lines


def read_activity_snapshot(store: Path, run_id: str) -> dict:
    conn = sqlite3.connect(f"file:{Path(store).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        groups_rows = conn.execute(
            """
            SELECT kind, member_count, status
            FROM observation_groups
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        rel_rows = conn.execute(
            """
            SELECT kind, src_person_id, evidence_json, confirmed
            FROM relationships
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT label, t_start, t_end, folder
            FROM events
            WHERE run_id=?
            ORDER BY rowid DESC
            LIMIT 12
            """,
            (run_id,),
        ).fetchall()
        track_count = int(
            conn.execute("SELECT COUNT(*) FROM tracks WHERE run_id=?", (run_id,)).fetchone()[0]
        )
    finally:
        conn.close()

    groups = [dict(r) for r in groups_rows]
    relationships: list[dict] = []
    for row in rel_rows:
        rel = dict(row)
        evidence = {}
        raw = rel.get("evidence_json")
        if raw:
            try:
                evidence = json.loads(raw)
            except json.JSONDecodeError:
                evidence = {}
        rel["name_a"] = evidence.get("name_a") or evidence.get("src_name")
        rel["name_b"] = evidence.get("name_b") or evidence.get("dst_name")
        ids = evidence.get("person_ids")
        if isinstance(ids, list):
            if not rel.get("src_person_id") and len(ids) > 0:
                rel["src_person_id"] = ids[0]
            rel["other_person_ids"] = [str(i) for i in ids[1:] if i]
        else:
            rel["other_person_ids"] = []
        relationships.append(rel)

    events = [dict(r) for r in event_rows]
    return {
        "groups": groups,
        "relationships": relationships,
        "events": events,
        "track_count": track_count,
    }


def json_fallback(rec: dict) -> str:
    return json.dumps(rec, indent=2)[:4000]


class HomeApp:
    """Small entry window. Mutations stay in review-ui / review.py."""

    def __init__(self, store: Path | None = None):
        if tk is None or ttk is None or filedialog is None or messagebox is None:
            raise RuntimeError("tkinter is required for home-ui")
        self.store = Path(store) if store is not None else default_store_path()
        self._busy = False
        self._cancel = threading.Event()
        self._exit_after_cancel = False
        self._wd = Watchdog(stall_s=120.0)
        self._last_run_id: str | None = None
        self._last_review_html: Path | None = None
        self._q: queue.Queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Semblon")
        self.root.minsize(480, 320)
        self.root.geometry("560x400")

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
        self.btn_canvas.configure(state=state)
        self.btn_search.configure(state=state)
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
        self._wd = Watchdog(stall_s=120.0)
        self._set_busy(True)
        self.status.set(format_progress_line(make_event(STAGE_PROCESS, KIND_QUEUED, path=str(path))))
        threading.Thread(target=self._run_process, args=(path,), daemon=True).start()

    def _run_process(self, folder: Path) -> None:
        def on_event(ev: ProgressEvent) -> None:
            self._wd.note(ev)
            self._q.put(("status", format_progress_line(ev)))

        try:
            rec = process_folder(
                folder,
                store=self.store,
                open_review=False,
                progress=lambda *_: None,
                on_event=on_event,
                cancel=self._cancel.is_set,
                observers=HOME_OBSERVERS,
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
        if self._busy:
            stalled = self._wd.check()
            if stalled is not None and stalled.kind == KIND_STALLED:
                self.status.set(format_progress_line(stalled) + "  (slow vs stalled — job not killed)")
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
        body = ttk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        lb = tk.Listbox(body)
        sb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
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
        from semblon.store import integrity_report

        if not self.store.is_file():
            messagebox.showinfo("Semblon", f"No store yet:\n{self.store}")
            return
        rid = latest_run_id(self.store)
        line = empty_state_line(self.store, rid) if rid else "no runs"
        try:
            integ = integrity_report(self.store)
            extra = f"integrity ok={integ['ok']} unfinished={len(integ['unfinished_runs'])}"
        except OSError as e:
            extra = f"integrity unavailable: {e}"

        if not rid:
            self._list_window(
                "Activity",
                format_activity_lines(
                    run_line=line,
                    integrity_line=extra,
                    groups=[],
                    relationships=[],
                    events=[],
                    track_count=0,
                ),
            )
            return

        try:
            rec = read_activity_snapshot(self.store, rid)
        except (sqlite3.DatabaseError, OSError) as e:
            self._list_window("Activity", [line, extra, f"activity unavailable: {e}"])
            return
        self._list_window(
            "Activity",
            format_activity_lines(
                run_line=line,
                integrity_line=extra,
                groups=rec.get("groups") or [],
                relationships=rec.get("relationships") or [],
                events=rec.get("events") or [],
                track_count=int(rec.get("track_count") or 0),
            ),
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
