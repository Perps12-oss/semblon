from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_contact_sheet import _boot_tidy, _spin

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")


def _member(path: Path, name: str, size: int, mtime: int) -> dict:
    return {"path": str(path), "mediaId": name, "name": name, "folder": "f", "thumb": "",
            "bytes": size, "mtime": mtime, "when": "", "size": ""}


def _two_kinds(tmp_path):
    files = {}
    for n in ("a", "b", "c", "d", "e"):
        p = tmp_path / f"{n}.jpg"
        p.write_bytes(b"x" * 1000)
        files[n] = p
    exact = {"exact": True, "members": [_member(files["a"], "a", 300, 10), _member(files["b"], "b", 100, 20)]}
    near = {"exact": False, "members": [_member(files["c"], "c", 900, 5), _member(files["d"], "d", 50, 6),
                                        _member(files["e"], "e", 60, 7)]}
    return files, [exact, near]


def test_tidy_shows_one_kind_unless_both_are_on(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell
    a = tmp_path / "x.jpg"; a.write_bytes(b"x" * 200_000)
    b = tmp_path / "y.jpg"; b.write_bytes(b"x" * 200_000)
    app, engine, root, bridge = _boot_tidy(tmp_path, monkeypatch, [a, b])
    try:
        _, sets = _two_kinds(tmp_path)
        bridge._tidy_sets = sets
        assert [g["exact"] for g in bridge.tidySets] == [True]
        bridge.toggleTidyNear()
        assert len(bridge.tidySets) == 2
        bridge.toggleTidyExact()
        assert [g["exact"] for g in bridge.tidySets] == [False]
        bridge.toggleTidyNear()  # the last kind cannot be turned off
        assert bridge.tidyNearOn and len(bridge.tidySets) == 1
    finally:
        shutdown_shell(engine)


def test_tidy_sort_orders(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell
    a = tmp_path / "x.jpg"; a.write_bytes(b"x" * 200_000)
    b = tmp_path / "y.jpg"; b.write_bytes(b"x" * 200_000)
    app, engine, root, bridge = _boot_tidy(tmp_path, monkeypatch, [a, b])
    try:
        _, sets = _two_kinds(tmp_path)
        bridge._tidy_sets = sets
        bridge.toggleTidyNear()
        assert [g["exact"] for g in bridge.tidySets] == [False, True]  # most copies first
        bridge.setTidySort("size")
        assert [g["exact"] for g in bridge.tidySets] == [False, True]  # 900 beats 300
        bridge.setTidySort("time")
        assert [g["exact"] for g in bridge.tidySets] == [True, False]  # 20 beats 7
        bridge.setTidySort("name")
        assert [g["exact"] for g in bridge.tidySets] == [True, False]  # a before c
        bridge.setTidySort("nonsense")
        assert bridge.tidySort == "name"
    finally:
        shutdown_shell(engine)


def test_tidy_multi_select_bins_only_ticked_and_keeps_one(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell
    a = tmp_path / "x.jpg"; a.write_bytes(b"x" * 200_000)
    b = tmp_path / "y.jpg"; b.write_bytes(b"x" * 200_000)
    app, engine, root, bridge = _boot_tidy(tmp_path, monkeypatch, [a, b])
    try:
        files, sets = _two_kinds(tmp_path)
        bridge._tidy_sets = sets
        bridge.toggleTidyNear()
        bridge.pickAllButFirst()
        assert bridge.tidyPickedCount == 3  # b, d, e
        bridge.toggleTidyPick(str(files["a"]))
        bridge.toggleTidyPick(str(files["b"]))  # a is ticked, b is not
        bridge.binPicked()
        assert bridge.confirm["open"] is True and "Recycle Bin" in bridge.confirm["body"]
        bridge.confirmDecline()
        assert all(p.exists() for p in files.values())

        bridge.toggleTidyPick(str(files["b"]))  # a and b both ticked: would empty the set
        bridge.binPicked()
        assert bridge.confirm["open"] is False
        assert all(p.exists() for p in files.values())

        bridge.clearTidyPicks()
        bridge.toggleTidyPick(str(files["b"]))
        bridge.toggleTidyPick(str(files["d"]))
        monkeypatch.setattr("PySide6.QtCore.QFile.moveToTrash", staticmethod(lambda p: (Path(p).unlink(), True)[1]))
        bridge.binPicked()
        bridge.confirmAccept()
        assert files["a"].exists() and files["c"].exists() and files["e"].exists()
        assert not files["b"].exists() and not files["d"].exists()
        assert bridge.tidyPickedCount == 0
        # the exact set fell to one photo, so it is gone; the near set still has two
        assert [g["exact"] for g in bridge.tidySets] == [False]
    finally:
        shutdown_shell(engine)


def _jpg(path: Path, img) -> None:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    assert ok
    path.write_bytes(buf.tobytes())


def _store(tmp_path, paths):
    from semblon.engine import _sha256_file
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    con = connect(store)
    init_db(con)
    for i, p in enumerate(paths):
        con.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                    (f"m{i}", "folder", str(p), _sha256_file(p), 64, 64, 0, p.stat().st_size))
    con.commit()
    con.close()
    return store


def test_near_ignores_blank_pictures_and_other_shapes(tmp_path):
    from semblon.duplicates import NEAR_APP_THRESHOLD, find_near_duplicate_groups

    rng = np.random.default_rng(3)
    scene = rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8)
    scene = cv2.GaussianBlur(scene, (0, 0), 6)
    scene = cv2.normalize(scene, None, 0, 255, cv2.NORM_MINMAX)
    paths = []
    for name, img in {
        "scene.jpg": scene,
        "scene_small.jpg": cv2.resize(scene, (64, 64), interpolation=cv2.INTER_AREA),
        "black1.jpg": np.zeros((96, 96, 3), dtype=np.uint8),
        "black2.jpg": np.full((96, 96, 3), 2, dtype=np.uint8),
        "wide.jpg": cv2.resize(scene, (192, 48), interpolation=cv2.INTER_AREA),
    }.items():
        p = tmp_path / name
        _jpg(p, img)
        paths.append(p)
    res = find_near_duplicate_groups(_store(tmp_path, paths), threshold=NEAR_APP_THRESHOLD)
    grouped = [{Path(m["path"]).name for m in g["members"]} for g in res["groups"]]
    assert grouped == [{"scene.jpg", "scene_small.jpg"}]


def test_near_does_not_chain_unrelated_pictures(tmp_path):
    from semblon.duplicates import find_near_duplicate_groups

    a = np.zeros((64, 64, 3), dtype=np.uint8)
    a[:, :32] = 255
    b = a.copy()
    b[:, 32:44] = 255   # a few cells different from a
    c = b.copy()
    c[:, 44:56] = 255   # close to b, far from a
    paths = []
    for name, img in (("a.jpg", a), ("b.jpg", b), ("c.jpg", c)):
        p = tmp_path / name
        _jpg(p, img)
        paths.append(p)
    res = find_near_duplicate_groups(_store(tmp_path, paths), threshold=2)
    for g in res.get("groups", []):
        names = {Path(m["path"]).name for m in g["members"]}
        assert names != {"a.jpg", "b.jpg", "c.jpg"}
