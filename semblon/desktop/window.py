"""Persistent application shell. Navigation stays; the workspace changes."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from semblon.desktop.backdrop import apply_mica
from semblon.desktop.copy import process_event_snapshot
from semblon.desktop.pages import (
    ActivityPage,
    HomePage,
    PeoplePage,
    PhotosPage,
    SettingsPage,
    UnknownPage,
    VideosPage,
)
from semblon.desktop.service import StoreLibraryService
from semblon.desktop.widgets import InspectorPanel, ProgressBanner, load_still_thumb, open_containing_folder
from semblon.desktop.workers import ImportWorker
from semblon.progress import KIND_QUEUED, STAGE_PROCESS, make_event

NAV = ("Home", "Photos", "Videos", "People", "Unknown", "Activity", "Settings")


class ImportDialog(QDialog):
    def __init__(self, parent=None, folder: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add photos and videos")
        self.setModal(True)
        self._folder = folder or ""
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Add photos and videos"))
        self.path_label = QLabel(self._folder or "No folder selected")
        self.path_label.setWordWrap(True)
        choose = QPushButton("Choose folder")
        choose.setDefault(True)
        choose.clicked.connect(self._choose)
        facts = QLabel(
            "Semblon always includes subfolders.\n"
            "Video files are sampled — not treated as one person per frame."
        )
        facts.setObjectName("muted")
        facts.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start import")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept)
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok.setEnabled(bool(self._folder))
        lay.addWidget(self.path_label)
        lay.addWidget(choose)
        lay.addWidget(facts)
        lay.addWidget(buttons)

    def _choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of photos and videos")
        if not folder:
            return
        self._folder = folder
        self.path_label.setText(folder)
        self._ok.setEnabled(True)

    def _accept(self) -> None:
        if not self._folder:
            return
        self.accept()

    def folder(self) -> Path:
        return Path(self._folder)


class SearchDialog(QDialog):
    def __init__(self, items: list[dict], query: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search")
        self.chosen = None
        lay = QVBoxLayout(self)
        if not items:
            lay.addWidget(
                QLabel(
                    f'No named person matching "{query}".\n'
                    "Search looks up people you have named."
                )
            )
        else:
            lst = QListWidget()
            for it in items:
                name = it.get("display_name") or it.get("person_id") or it.get("label")
                faces = it.get("faces") or 0
                row = QListWidgetItem(f"{name}  ({faces} observations)")
                row.setData(Qt.ItemDataRole.UserRole, it)
                lst.addItem(row)
            lst.itemActivated.connect(self._pick)
            lay.addWidget(lst)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)

    def _pick(self, item: QListWidgetItem) -> None:
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: Path | None = None,
        *,
        service: StoreLibraryService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.service = service or StoreLibraryService(store)
        self._thread: QThread | None = None
        self._worker: ImportWorker | None = None
        self._busy = False
        self._last_counts = ""
        self._pending_unknown: dict | None = None
        self._pending_person: dict | None = None
        self._exit_after_cancel = False
        self._last_info = ""
        self.setWindowTitle("Semblon")
        self.setMinimumSize(QSize(900, 600))
        self.resize(1280, 800)
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._build()
        self._shortcuts()
        self.refresh_all()
        QTimer.singleShot(0, self._apply_backdrop)

    def current_page(self) -> str:
        row = self.nav.currentRow()
        if 0 <= row < len(NAV):
            return NAV[row]
        return "Home"

    def navigate(self, name: str) -> None:
        if name not in NAV:
            return
        self.nav.setCurrentRow(NAV.index(name))

    def _build(self) -> None:
        chrome = QWidget()
        chrome.setObjectName("chrome")
        chrome_l = QHBoxLayout(chrome)
        chrome_l.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("Semblon")
        brand.setObjectName("title")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search named people…")
        self.search.setAccessibleName("Search named people")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._run_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._run_search)
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(lambda: self.navigate("Settings"))
        chrome_l.addWidget(brand)
        chrome_l.addStretch(1)
        chrome_l.addWidget(self.search, 1)
        chrome_l.addWidget(search_btn)
        chrome_l.addWidget(settings_btn)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setAccessibleName("Navigation")
        self.nav.setFixedWidth(168)
        for name in NAV:
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._nav_changed)

        self.stack = QStackedWidget()
        self.home = HomePage()
        self.photos = PhotosPage()
        self.videos = VideosPage()
        self.people = PeoplePage()
        self.unknown = UnknownPage()
        self.activity = ActivityPage()
        self.settings = SettingsPage()
        for page in (
            self.home,
            self.photos,
            self.videos,
            self.people,
            self.unknown,
            self.activity,
            self.settings,
        ):
            self.stack.addWidget(page)

        self.home.add_folder.connect(self.open_import)
        self.photos.add_folder.connect(self.open_import)
        self.videos.add_folder.connect(self.open_import)
        self.home.open_unknown.connect(lambda: self.navigate("Unknown"))
        self.photos.inspect.connect(self._inspect_media)
        self.videos.inspect.connect(self._inspect_media)
        self.people.inspect.connect(self._inspect_person)
        self.people.rename.connect(self._rename_person)
        self.unknown.inspect.connect(self._inspect_unknown)
        self.unknown.name.connect(self._name_unknown)
        self.unknown.ignore.connect(self._ignore_unknown)
        self.unknown.merge.connect(self._merge_unknown)
        self.unknown.note.connect(self._note_unknown)

        self.banner = ProgressBanner()
        self.banner.cancel_requested.connect(self._cancel_import)
        self.banner.review_requested.connect(lambda: self.navigate("Unknown"))
        self.banner.dismissed.connect(self.banner.hide)

        workspace = QWidget()
        ws = QVBoxLayout(workspace)
        ws.setContentsMargins(12, 8, 12, 8)
        ws.addWidget(self.banner)
        ws.addWidget(self.stack, 1)

        self.inspector = InspectorPanel()
        self.inspector.open_folder_requested.connect(self._open_folder)
        self.inspector.name_requested.connect(self._inspector_name)
        self.inspector.ignore_requested.connect(self._inspector_ignore)

        split = QSplitter()
        split.addWidget(self.nav)
        split.addWidget(workspace)
        split.addWidget(self.inspector)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([168, 760, 300])

        root = QWidget()
        root_l = QVBoxLayout(root)
        root_l.setContentsMargins(0, 0, 0, 0)
        root_l.setSpacing(0)
        root_l.addWidget(chrome)
        root_l.addWidget(split, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"Library: {self.service.store}")

        file_menu = self.menuBar().addMenu("&File")
        act_import = QAction("Add folder…", self)
        act_import.setShortcut(QKeySequence("Ctrl+O"))
        act_import.triggered.connect(self.open_import)
        file_menu.addAction(act_import)
        file_menu.addSeparator()
        act_quit = QAction("Exit", self)
        act_quit.setShortcut(QKeySequence("Alt+F4"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)
        view_menu = self.menuBar().addMenu("&View")
        for i, name in enumerate(NAV):
            act = QAction(name, self)
            act.setShortcut(QKeySequence(f"Ctrl+{i + 1}"))
            act.triggered.connect(lambda _c=False, n=name: self.navigate(n))
            view_menu.addAction(act)

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._escape)

    def notify(self, text: str, *, title: str = "Semblon") -> None:
        self._last_info = text
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        QMessageBox.information(self, title, text)

    def warn(self, text: str, *, title: str = "Semblon") -> None:
        self._last_info = text
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        QMessageBox.warning(self, title, text)

    def _apply_backdrop(self) -> None:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        apply_mica(int(self.winId()))

    def _nav_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            self._refresh_page(NAV[row])

    def refresh_all(self) -> None:
        self.home.refresh(self.service)
        self.photos.refresh(self.service)
        self.videos.refresh(self.service)
        self.people.refresh(self.service)
        self.unknown.refresh(self.service)
        self.activity.refresh(self.service)
        self.settings.refresh(self.service)
        rec = self.service.home_summary()
        self.statusBar().showMessage(
            f"Library: {self.service.store}   "
            f"{rec.get('photos') or 0} photos · {rec.get('videos') or 0} videos · "
            f"{rec.get('people') or 0} people"
        )

    def _refresh_page(self, name: str) -> None:
        pages = {
            "Home": self.home,
            "Photos": self.photos,
            "Videos": self.videos,
            "People": self.people,
            "Unknown": self.unknown,
            "Activity": self.activity,
            "Settings": self.settings,
        }
        page = pages.get(name)
        if page is not None:
            page.refresh(self.service)

    def open_import(self) -> None:
        if self._busy:
            self.notify(
                "An import is already running. You can browse the library or cancel that import."
            )
            return
        dlg = ImportDialog(self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._start_import(dlg.folder())

    def _start_import(self, folder: Path) -> None:
        self._busy = True
        self._last_counts = ""
        queued = process_event_snapshot(
            make_event(STAGE_PROCESS, KIND_QUEUED, path=str(folder), message="Waiting to start")
        )
        self.banner.show_busy(queued)
        self._thread = QThread(self)
        self._worker = ImportWorker(folder, self.service.store)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_success)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.failed.connect(self._on_failed)
        self._worker.succeeded.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()
        self.statusBar().showMessage("Import running — the rest of Semblon stays usable.")

    def _on_progress(self, snap: dict) -> None:
        self.banner.show_busy(snap)
        if snap.get("counts"):
            self._last_counts = snap["counts"]
        self.statusBar().showMessage(snap.get("headline") or "Working…")

    def _cancel_import(self) -> None:
        if self._worker is None:
            return
        self._worker.request_cancel()
        self.banner.show_stopping()

    def _on_success(self, rec: dict) -> None:
        self._busy = False
        ing = rec.get("ingest") or {}
        files = ing.get("files") or ing.get("new_media") or 0
        skipped = ing.get("skipped_seen") or 0
        summary = f"{files} files processed"
        if skipped:
            summary += f" · {skipped} skipped"
        self.banner.show_complete(summary)
        self.refresh_all()
        self.navigate("Unknown")

    def _on_cancelled(self, rec: dict) -> None:
        self._busy = False
        line = self._last_counts or "Partial results have been retained."
        self.banner.show_cancelled(line)
        self.refresh_all()
        if self._exit_after_cancel:
            self.close()

    def _on_failed(self, user: str, detail: str) -> None:
        self._busy = False
        self.banner.show_failed(user)
        self._last_info = user
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Semblon")
            box.setText("Semblon couldn't complete this operation.")
            box.setInformativeText(user)
            box.setDetailedText(detail)
            box.setStandardButtons(QMessageBox.StandardButton.Close)
            box.exec()
        self.refresh_all()
        if self._exit_after_cancel:
            self.close()

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _run_search(self) -> None:
        q = self.search.text().strip()
        if not q:
            self.notify(
                "Type a person's name. Search looks up people you have named — not visual similarity."
            )
            return
        from semblon.search import SearchError, search_person

        try:
            rec = search_person(self.service.store, q)
        except SearchError as e:
            self.warn(str(e))
            return
        dlg = SearchDialog(rec.get("items") or [], q, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen:
            self.navigate("People")
            self._inspect_person(dlg.chosen)

    def _focus_search(self) -> None:
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def _escape(self) -> None:
        self.inspector.clear()
        self.search.clearFocus()

    def _inspect_media(self, item: dict) -> None:
        pix = QPixmap()
        if item.get("kind") != "video" and item.get("path"):
            pix = load_still_thumb(item["path"], 320)
        self.inspector.show_media(item, pix)
        self._pending_unknown = None
        self._pending_person = None

    def _inspect_person(self, item: dict) -> None:
        rec = dict(item)
        rec.setdefault("display_name", item.get("label"))
        self.inspector.show_person(rec, QPixmap())
        self._pending_unknown = None
        self._pending_person = rec

    def _inspect_unknown(self, item: dict) -> None:
        rec = dict(item)
        rec.setdefault("title", item.get("label") or "Unknown")
        rec.setdefault("subtitle", item.get("note") or "not a person until Name")
        rec.setdefault("hint", "A cluster is not a person.")
        self.inspector.show_unknown(rec, QPixmap())
        self._pending_unknown = rec
        self._pending_person = None

    def _ask_text(self, title: str, label: str, text: str = "") -> str | None:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return None
        name, ok = QInputDialog.getText(self, title, label, text=text)
        if not ok or not name.strip():
            return None
        return name.strip()

    def _review_run(self, item: dict | None = None) -> str | None:
        from semblon.review_ui import ReviewUiError, resolve_run_id

        rid = (item or {}).get("run_id")
        try:
            return str(rid) if rid else resolve_run_id(self.service.store, None)
        except ReviewUiError as e:
            self.warn(str(e))
            return None

    def _name_unknown(self, item: dict | None = None) -> None:
        item = item or self._pending_unknown
        if not item:
            return
        name = self._ask_text("Name person", "Name this group as:")
        if not name:
            return
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError, apply_name

        run_id = self._review_run(item)
        if run_id is None:
            return
        try:
            apply_name(self.service.store, run_id, item, name)
        except (ReviewError, ReviewUiError) as e:
            self.warn(str(e))
            return
        self.refresh_all()
        self.navigate("People")

    def _merge_unknown(self, cluster_ids: object) -> None:
        ids = [str(c) for c in (cluster_ids or []) if c]
        if len(ids) < 2:
            self.notify("Select two or more unnamed groups to merge. This corrects clustering, not people.")
            return
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError, apply_merge

        run_id = self._review_run()
        if run_id is None:
            return
        try:
            apply_merge(self.service.store, run_id, ids)
        except (ReviewError, ReviewUiError) as e:
            self.warn(str(e))
            return
        self.refresh_all()

    def _note_unknown(self, item: dict | None = None) -> None:
        item = item or self._pending_unknown
        if not item:
            return
        text = self._ask_text("Note", "Note for this group:")
        if not text:
            return
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError, apply_note

        run_id = self._review_run(item)
        if run_id is None:
            return
        try:
            apply_note(self.service.store, run_id, item, text)
        except (ReviewError, ReviewUiError) as e:
            self.warn(str(e))
            return
        self.refresh_all()

    def _ignore_unknown(self, item: dict | None = None) -> None:
        item = item or self._pending_unknown
        if not item:
            return
        from semblon.review import ReviewError
        from semblon.review_ui import ReviewUiError, apply_ignore

        run_id = self._review_run(item)
        if run_id is None:
            return
        try:
            apply_ignore(self.service.store, run_id, item)
        except (ReviewError, ReviewUiError) as e:
            self.warn(str(e))
            return
        self.refresh_all()

    def _rename_person(self, item: dict) -> None:
        current = item.get("display_name") or item.get("label") or ""
        name = self._ask_text("Rename", "Display name:", current)
        if not name:
            return
        from semblon.review import ReviewError, name_cluster
        from semblon.review_ui import ReviewUiError, apply_name, load_board, resolve_run_id

        try:
            run_id = resolve_run_id(self.service.store, None)
            board = load_board(self.service.store, run_id)
        except ReviewUiError as e:
            self.warn(str(e))
            return
        for it in board.get("items") or []:
            names = it.get("person_names") or []
            if current not in names and item.get("display_name") not in names:
                continue
            try:
                if it.get("kind") == "cluster" and it.get("cluster_id"):
                    name_cluster(self.service.store, run_id, it["cluster_id"], name)
                else:
                    apply_name(self.service.store, run_id, it, name)
            except (ReviewError, ReviewUiError) as e:
                self.warn(str(e))
                return
            self.refresh_all()
            return
        self.notify(
            "Rename uses the existing Name action on a linked face group. "
            "Semblon will not invent a second identity path."
        )

    def _inspector_name(self) -> None:
        if self._pending_person:
            self._rename_person(self._pending_person)
            return
        self._name_unknown(self._pending_unknown)

    def _inspector_ignore(self) -> None:
        self._ignore_unknown(self._pending_unknown)

    def _open_folder(self) -> None:
        path = self.inspector.path()
        if path:
            open_containing_folder(path)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                if self._worker is not None:
                    self._worker.request_cancel()
                event.accept()
                return
            box = QMessageBox.question(
                self,
                "Semblon",
                "Processing is still running. Cancel and exit?",
            )
            if box != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._exit_after_cancel = True
            if self._worker is not None:
                self._worker.request_cancel()
                self.banner.show_stopping()
            event.ignore()
            return
        event.accept()
