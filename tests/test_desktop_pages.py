"""Desktop workspace pages. No FaceKit. Offscreen Qt when available."""

from __future__ import annotations

from pathlib import Path

import pytest

from semblon.desktop.service import PHOTO_SORT_LABELS, StoreLibraryService
from semblon.store import connect, init_db


class FakeService:
    def __init__(self) -> None:
        self.photo_sorts: list[str] = []
        self.photos = [{"id": "m1", "label": "a.jpg", "path": "/a.jpg", "kind": "photo"}]
        self.unknown = [
            {
                "id": "cluster:c1",
                "kind": "cluster",
                "cluster_id": "c1",
                "label": "group c1",
                "faces": 2,
            }
        ]

    def home_summary(self) -> dict:
        return {
            "available": True,
            "photos": 1,
            "videos": 0,
            "people": 0,
            "unknown": 1,
            "recent": [{"label": "run-1  finished", "run_id": "run-1"}],
            "store": "/tmp/store.sqlite",
        }

    def list_photos(self, *, sort: str = "newest", limit: int = 200) -> list[dict]:
        self.photo_sorts.append(sort)
        return list(self.photos)

    def list_videos(self, *, limit: int = 200) -> list[dict]:
        return []

    def list_people(self) -> list[dict]:
        return []

    def list_unknown(self, *, limit: int = 200) -> list[dict]:
        return list(self.unknown)

    def list_activity(self, *, limit: int = 40) -> list[dict]:
        return [{"label": "run-1  finished", "run_id": "run-1"}][:limit]

    def settings_lines(self) -> list[str]:
        return ["Store: /tmp/store.sqlite", "cluster ≠ person"]


def test_pages_source_wires_sort_and_unknown_actions():
    src = (Path(__file__).resolve().parents[1] / "semblon" / "desktop" / "pages.py").read_text(
        encoding="utf-8"
    )
    assert "currentIndexChanged.connect(self._on_sort_changed)" in src
    assert "self.name.emit" in src
    assert "self.ignore.emit" in src
    assert "self.recent = QListWidget()" in src
    assert "folder_empty_state" in src


def test_thumbgrid_avoids_double_emit_wiring():
    src = (Path(__file__).resolve().parents[1] / "semblon" / "desktop" / "widgets.py").read_text(
        encoding="utf-8"
    )
    assert "itemActivated.connect(self._activate)" in src
    assert "itemDoubleClicked.connect(self._activate)" not in src


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:
        pytest.skip(str(e))
    app = QApplication.instance() or QApplication([])
    return app


def test_store_service_lists_photos_sorted(tmp_path):
    store = tmp_path / "store.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t0','t1','0','p',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/z.jpg','h1',1,1,30,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/a.jpg','h2',1,1,10,1)")
    conn.execute("INSERT INTO media VALUES ('v1','video','/c.mp4','h3',1,1,20,1)")
    conn.commit()
    conn.close()
    svc = StoreLibraryService(store)
    newest = svc.list_photos(sort="newest")
    assert [r["label"] for r in newest] == ["z.jpg", "a.jpg"]
    named = svc.list_photos(sort="name")
    assert [r["label"] for r in named] == ["a.jpg", "z.jpg"]
    videos = svc.list_videos()
    assert [r["label"] for r in videos] == ["c.mp4"]
    assert svc.list_photos(sort="bogus")[0]["label"] == "z.jpg"


def test_home_summary_counts_are_uncapped(tmp_path):
    store = tmp_path / "store.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t0','t1','0','p',2,'l2','{}','{}','x64','native')"""
    )
    for i in range(205):
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (f"m{i}", "folder", f"/p{i}.jpg", f"h{i}", 1, 1, i, 1),
        )
    conn.commit()
    conn.close()
    svc = StoreLibraryService(store)
    rec = svc.home_summary()
    assert rec["photos"] == 205
    assert len(svc.list_photos()) == 200


def test_settings_lines_drop_falsey():
    lines = FakeService().settings_lines()
    text = "\n".join(lines)
    assert "Store:" in text
    assert "cluster ≠ person" in text
    assert "None" not in text


def test_photos_sort_change_refreshes(qapp):
    from semblon.desktop.pages import PhotosPage

    page = PhotosPage()
    svc = FakeService()
    assert page.sort.count() == len(PHOTO_SORT_LABELS)
    page.refresh(svc)
    assert svc.photo_sorts == ["newest"]
    page.sort.setCurrentIndex(2)
    assert svc.photo_sorts[-1] == "name"
    assert page.sort_key() == "name"


def test_unknown_name_and_ignore_emit(qapp):
    from semblon.desktop.pages import UnknownPage

    page = UnknownPage()
    svc = FakeService()
    named: list = []
    ignored: list = []
    page.name.connect(named.append)
    page.ignore.connect(ignored.append)
    page.refresh(svc)
    assert page.btn_name.isEnabled() is False
    assert page.btn_ignore.isEnabled() is False
    page.grid.setCurrentRow(0)
    assert page.btn_name.isEnabled() is True
    assert page.btn_ignore.isEnabled() is True
    page.btn_name.click()
    page.btn_ignore.click()
    assert named and named[0]["cluster_id"] == "c1"
    assert ignored and ignored[0]["kind"] == "cluster"


def test_people_empty_action_emits_open_unknown(qapp):
    from semblon.desktop.pages import PeoplePage

    page = PeoplePage()
    opened = {"n": 0}
    page.open_unknown.connect(lambda: opened.__setitem__("n", opened["n"] + 1))
    page.refresh(FakeService())
    assert page.empty._button is not None
    page.empty._button.click()
    assert opened["n"] == 1


def test_home_recent_is_list_and_empty_add_folder(qapp):
    from PySide6.QtWidgets import QListWidget

    from semblon.desktop.pages import HomePage

    page = HomePage()
    assert isinstance(page.recent, QListWidget)
    fired = {"n": 0}
    page.add_folder.connect(lambda: fired.__setitem__("n", fired["n"] + 1))
    empty_svc = FakeService()
    empty_svc.home_summary = lambda: {  # type: ignore[method-assign]
        "available": True,
        "photos": 0,
        "videos": 0,
        "people": 0,
        "unknown": 0,
        "recent": [],
        "store": "x",
    }
    page.refresh(empty_svc)
    assert page.empty.isVisible()
    page.empty._button.click()
    assert fired["n"] == 1
    page.refresh(FakeService())
    assert page.recent.count() == 1


def test_home_recent_item_emits_payload(qapp):
    from semblon.desktop.pages import HomePage

    page = HomePage()
    opened: list[dict] = []
    page.open_recent.connect(opened.append)
    page.refresh(FakeService())
    page.recent.setCurrentRow(0)
    page._open_recent_item(page.recent.currentItem())
    assert opened
    assert opened[0]["run_id"] == "run-1"


def test_home_unavailable_store_message(qapp):
    from semblon.desktop.pages import HomePage

    page = HomePage()
    svc = FakeService()
    svc.home_summary = lambda: {  # type: ignore[method-assign]
        "available": False,
        "photos": 0,
        "videos": 0,
        "people": 0,
        "unknown": 0,
        "recent": [],
        "store": "x",
    }
    page.refresh(svc)
    assert "unavailable" in page.stats.text().lower()
    assert page.empty.isVisible()
    assert page.btn_unknown.isEnabled() is False


def test_settings_text_is_selectable(qapp):
    from PySide6.QtCore import Qt

    from semblon.desktop.pages import SettingsPage

    page = SettingsPage()
    page.refresh(FakeService())
    flags = page.body.textInteractionFlags()
    assert bool(flags & Qt.TextInteractionFlag.TextSelectableByMouse)
