"""S8 shell bridge: RO board + review.py mutations. No FaceKit in this process."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from semblon.process import default_store_path
from semblon.review import ReviewError
from semblon.review_board import (
    ReviewUiError,
    apply_ignore,
    apply_merge,
    apply_name,
    apply_note,
    apply_split,
    load_board,
    resolve_run_id,
)


def item_label(item: dict) -> str:
    names = item.get("person_names") or []
    if names:
        return str(names[0])
    kind = str(item.get("kind") or "group")
    return str(item.get("cluster_id") or item.get("face_id") or item.get("track_id") or kind)


def _uri(path: str) -> str | None:
    p = Path(path)
    if p.is_file():
        return p.as_uri()
    return None


def _item_for_qml(it: dict) -> dict:
    uris: list[str] = []
    for m in it.get("members") or []:
        u = _uri(m.get("path") or "")
        if u and u not in uris:
            uris.append(u)
        if len(uris) >= 8:
            break
    return {
        "kind": it["kind"],
        "label": item_label(it),
        "band": it.get("band") or "",
        "clusterId": it.get("cluster_id") or "",
        "faceId": it.get("face_id") or "",
        "faceCount": int(it.get("face_count") or 0),
        "named": bool(it.get("named")),
        "personNames": ", ".join(it.get("person_names") or []),
        "imageUris": uris,
    }


class ShellBridge(QObject):
    """Presentation adapter. Mutations call semblon.review_board → review.py only."""

    boardChanged = Signal()
    sectionChanged = Signal()
    selectionChanged = Signal()
    messageChanged = Signal()

    def __init__(self, store: Path | None, run_id: str | None, parent=None):
        super().__init__(parent)
        self._store_path = Path(store) if store else default_store_path()
        self._run_arg = run_id
        self._run_id = ""
        self._pack_id = ""
        self._section = "Review"
        self._sections = ["Library", "Photos", "People", "Review", "Activity"]
        self._items: list[dict] = []
        self._qml_items: list[dict] = []
        self._selected = -1
        self._selected2 = -1
        self._message = ""
        self._counts = {
            "clusters": 0,
            "review_required": 0,
            "strong": 0,
            "unassigned": 0,
            "named_persons": 0,
        }
        self.reload()

    def _set_message(self, text: str) -> None:
        if text != self._message:
            self._message = text
            self.messageChanged.emit()

    @Slot()
    def reload(self) -> None:
        try:
            rid = resolve_run_id(self._store_path, self._run_arg)
            board = load_board(self._store_path, rid)
        except (ReviewUiError, FileNotFoundError, OSError) as e:
            self._run_id = ""
            self._pack_id = ""
            self._items = []
            self._qml_items = []
            self._selected = -1
            self._selected2 = -1
            self._counts = {
                "clusters": 0,
                "review_required": 0,
                "strong": 0,
                "unassigned": 0,
                "named_persons": 0,
            }
            self._set_message(str(e))
            self.boardChanged.emit()
            self.selectionChanged.emit()
            return
        self._run_id = board["run_id"]
        self._pack_id = board.get("pack_id") or ""
        self._items = list(board["items"])
        self._qml_items = [_item_for_qml(it) for it in self._items]
        self._counts = dict(board["counts"])
        if self._selected >= len(self._items):
            self._selected = -1
        if self._selected2 >= len(self._items):
            self._selected2 = -1
        self._set_message(f"store={self._store_path}  run={self._run_id}")
        self.boardChanged.emit()
        self.selectionChanged.emit()

    def _current_item(self) -> dict | None:
        if 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    @Property(str, notify=boardChanged)
    def runId(self):
        return self._run_id

    @Property(str, notify=boardChanged)
    def packId(self):
        return self._pack_id

    @Property(str, notify=boardChanged)
    def storePath(self):
        return str(self._store_path)

    @Property(str, notify=messageChanged)
    def message(self):
        return self._message

    @Property(int, notify=boardChanged)
    def clusters(self):
        return int(self._counts.get("clusters") or 0)

    @Property(int, notify=boardChanged)
    def unassigned(self):
        return int(self._counts.get("unassigned") or 0)

    @Property(int, notify=boardChanged)
    def reviewRequired(self):
        return int(self._counts.get("review_required") or 0)

    @Property(int, notify=boardChanged)
    def persons(self):
        return int(self._counts.get("named_persons") or 0)

    @Property(int, notify=boardChanged)
    def okFaces(self):
        return int(self._counts.get("clusters") or 0)  # kept for QML compat; prefer counts above

    @Property("QVariantList", notify=boardChanged)
    def items(self):
        return list(self._qml_items)

    @Property("QStringList", notify=boardChanged)
    def images(self):
        # Selected item thumbs, else first board item.
        it = None
        if 0 <= self._selected < len(self._qml_items):
            it = self._qml_items[self._selected]
        elif self._qml_items:
            it = self._qml_items[0]
        return list((it or {}).get("imageUris") or [])

    @Property("QStringList", constant=True)
    def sections(self):
        return list(self._sections)

    @Property(str, notify=sectionChanged)
    def section(self):
        return self._section

    @Property(int, notify=selectionChanged)
    def selectedIndex(self):
        return self._selected

    @Property(int, notify=selectionChanged)
    def donorIndex(self):
        return self._selected2

    @Property(str, notify=selectionChanged)
    def selectedLabel(self):
        if 0 <= self._selected < len(self._qml_items):
            return self._qml_items[self._selected]["label"]
        return ""

    @Property(bool, notify=selectionChanged)
    def selectedNamed(self):
        if 0 <= self._selected < len(self._qml_items):
            return bool(self._qml_items[self._selected]["named"])
        return False

    @Slot(str)
    def selectSection(self, name: str) -> None:
        if name in self._sections and name != self._section:
            self._section = name
            self.sectionChanged.emit()

    @Slot(int)
    def selectItem(self, index: int) -> None:
        if index < -1 or index >= len(self._items):
            return
        self._selected = index
        self.selectionChanged.emit()
        self.boardChanged.emit()  # refresh images binding

    @Slot(int)
    def toggleMergeDonor(self, index: int) -> None:
        """Second selection for Merge (survivor = selectedIndex)."""
        if index < 0 or index >= len(self._items):
            return
        if index == self._selected:
            return
        self._selected2 = -1 if self._selected2 == index else index
        self.selectionChanged.emit()
        self._set_message(
            f"merge donor={'none' if self._selected2 < 0 else self._qml_items[self._selected2]['label']}"
        )

    @Slot(str)
    def nameSelected(self, display_name: str) -> None:
        item = self._current_item()
        if item is None:
            self._set_message("select a cluster or face first")
            return
        name = (display_name or "").strip()
        if not name:
            self._set_message("name is empty")
            return
        try:
            apply_name(self._store_path, self._run_id, item, name)
        except (ReviewError, ReviewUiError) as e:
            self._set_message(str(e))
            return
        self.reload()
        self._set_message(f"named → {name}")

    @Slot()
    def ignoreSelected(self) -> None:
        item = self._current_item()
        if item is None:
            self._set_message("select a cluster or face first")
            return
        try:
            apply_ignore(self._store_path, self._run_id, item)
        except (ReviewError, ReviewUiError) as e:
            self._set_message(str(e))
            return
        self.reload()
        self._set_message("ignored")

    @Slot(str)
    def noteSelected(self, text: str) -> None:
        item = self._current_item()
        if item is None:
            self._set_message("select a cluster or face first")
            return
        note = (text or "").strip()
        if not note:
            self._set_message("note is empty")
            return
        try:
            apply_note(self._store_path, self._run_id, item, note)
        except (ReviewError, ReviewUiError) as e:
            self._set_message(str(e))
            return
        self.reload()
        self._set_message("note saved")

    @Slot()
    def mergeSelected(self) -> None:
        if self._selected < 0 or self._selected2 < 0:
            self._set_message("select survivor, then toggle a donor")
            return
        a = self._items[self._selected]
        b = self._items[self._selected2]
        if a.get("kind") != "cluster" or b.get("kind") != "cluster":
            self._set_message("merge needs two clusters")
            return
        try:
            apply_merge(
                self._store_path,
                self._run_id,
                [a["cluster_id"], b["cluster_id"]],
            )
        except (ReviewError, ReviewUiError) as e:
            self._set_message(str(e))
            return
        self._selected2 = -1
        self.reload()
        self._set_message("merged")

    @Slot()
    def splitFirstFace(self) -> None:
        """Split first member face out of selected cluster (same as a minimal UI split)."""
        item = self._current_item()
        if item is None or item.get("kind") != "cluster":
            self._set_message("select a cluster to split")
            return
        members = item.get("members") or []
        if len(members) < 2:
            self._set_message("need at least two faces to split")
            return
        face_id = members[0]["face_id"]
        try:
            apply_split(self._store_path, self._run_id, item["cluster_id"], [face_id])
        except (ReviewError, ReviewUiError) as e:
            self._set_message(str(e))
            return
        self.reload()
        self._set_message(f"split face {face_id[:8]}")
