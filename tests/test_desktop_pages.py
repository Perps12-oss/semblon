"""Desktop workspace pages. No FaceKit. Offscreen Qt when available."""

from __future__ import annotations

from pathlib import Path

import pytest

from semblon.desktop.service import StoreLibraryService
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

    def list_unknown(self) -> list[dict]:
        return list(self.unknown)

    def list_activity(self) -> list[dict]:
        return [{"label": "run-1  finished", "run_id": "run-1"}]

    def settings_lines(self) -> list[str | None]:
        return ["Store: /tmp/store.sqlite", None, "", "cluster ≠ person"]


def test_pages_source_wires_sort_and_unknown_actions():
    src = (Path(__file__).resolve().parents[1] / "semblon" / "desktop" / "pages.py").read_text(
        encoding="utf-8"
    )
    assert "currentIndexChanged.connect(self._on_sort_changed)" in src
    assert "self.name.emit" in src
    assert "self.ignore.emit" in src
    assert "self.recent = QListWidget()" in src
    assert "folder_empty_state" in src


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


def test_unknown_rows_carry_crop_fields(tmp_path):
    from tests.test_review import _clustered

    store = tmp_path / "store.sqlite"
    _clustered(store)
    rows = StoreLibraryService(store).list_unknown()
    assert rows
    row = rows[0]
    assert row.get("path")
    assert row.get("bbox")
    assert row.get("kind") in {"cluster", "track", "unassigned", "face"}
    assert "person" not in (row.get("kind") or "")


def test_thumbgrid_sets_icon_from_bytes(qapp, tmp_path):
    from PySide6.QtGui import QImage

    from semblon.desktop.widgets import ThumbGrid, pixmap_for_row

    img = QImage(24, 24, QImage.Format.Format_RGB32)
    img.fill(0xFF336699)
    png = Path(tmp_path / "t.png")
    img.save(str(png), "PNG")
    data = png.read_bytes()
    pix2 = pixmap_for_row({"thumb_bytes": data})
    assert not pix2.isNull()
    grid = ThumbGrid()
    grid.set_items([{"label": "group a", "thumb_bytes": data, "kind": "cluster"}])
    assert grid.count() == 1
    assert not grid.item(0).icon().isNull()


def test_settings_lines_drop_falsey():
    lines = FakeService().settings_lines()
    text = "\n".join(ln for ln in lines if ln)
    assert "Store:" in text
    assert "cluster ≠ person" in text
    assert "None" not in text


def test_photos_sort_change_refreshes(qapp):
    from semblon.desktop.pages import PhotosPage

    page = PhotosPage()
    svc = FakeService()
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
    page.grid.setCurrentRow(0)
    page.btn_name.click()
    page.btn_ignore.click()
    assert named and named[0]["cluster_id"] == "c1"
    assert ignored and ignored[0]["kind"] == "cluster"


def test_home_recent_is_list_and_empty_add_folder(qapp):
    from PySide6.QtWidgets import QListWidget

    from semblon.desktop.pages import HomePage

    page = HomePage()
    page.show()
    assert isinstance(page.recent, QListWidget)
    fired = {"n": 0}
    page.add_folder.connect(lambda: fired.__setitem__("n", fired["n"] + 1))
    empty_svc = FakeService()
    empty_svc.home_summary = lambda: {  # type: ignore[method-assign]
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
