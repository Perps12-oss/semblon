"""Reset app to defaults — Semblon-owned rebuildable state only."""

from __future__ import annotations

import inspect
import shutil
import sqlite3
from pathlib import Path

import pytest

from semblon.app_reset import (
    RESET_MANIFEST,
    assert_media_untouched,
    reset_app_to_defaults,
    resettable_paths,
)
from semblon.ui_prefs import appearance_path, load_theme_mode, save_theme_mode


def _seed_library(tmp: Path) -> tuple[Path, Path, dict[Path, bytes]]:
    """Library folder with media + Semblon sidecars + minimal store."""
    lib_dir = tmp / "photos"
    lib_dir.mkdir()
    media_a = lib_dir / "keep_a.jpg"
    media_b = lib_dir / "keep_b.png"
    media_a.write_bytes(b"\xff\xd8\xffORIGINAL-A")
    media_b.write_bytes(b"\x89PNGORIGINAL-B")
    notes = lib_dir / "user_notes.txt"
    notes.write_text("do not delete me\n", encoding="utf-8")

    store_dir = tmp / "semblon-lib"
    store_dir.mkdir()
    store = store_dir / "store.sqlite"
    conn = sqlite3.connect(str(store))
    try:
        conn.executescript(
            """
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE persons (person_id TEXT PRIMARY KEY, display_name TEXT);
            CREATE TABLE decisions (
                decision_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT
            );
            CREATE TABLE observation_items (
                item_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                provider TEXT
            );
            INSERT INTO schema_meta(key,value) VALUES ('schema_version','4');
            INSERT INTO schema_meta(key,value) VALUES ('home_completion_kind','ok');
            INSERT INTO schema_meta(key,value) VALUES ('home_completion_json','{}');
            INSERT INTO schema_meta(key,value) VALUES ('home_completion_ack_run','run-1');
            INSERT INTO persons(person_id, display_name) VALUES ('p1','Alex');
            INSERT INTO decisions(decision_id, kind, payload)
                VALUES ('d1','name','{"person_id":"p1"}');
            INSERT INTO observation_items(item_id, kind, provider)
                VALUES ('r1','user_region','user');
            """
        )
        conn.commit()
    finally:
        conn.close()

    save_theme_mode("cyber_obsidian", store)
    from semblon.media_grid import save_grid_density

    save_grid_density("compact", store)

    vc = store_dir / "visual_cache" / "m1" / "deadbeef"
    vc.mkdir(parents=True)
    (vc / "meta.json").write_text('{"cache":true}\n', encoding="utf-8")
    (store_dir / "store.sqlite.semblon-index.npz").write_bytes(b"NPZ-FAKE")
    (store_dir / "review.html").write_text("<html>export</html>\n", encoding="utf-8")

    probes = {
        media_a: media_a.read_bytes(),
        media_b: media_b.read_bytes(),
        notes: notes.read_bytes(),
    }
    return store, lib_dir, probes


def test_reset_restores_canonical_defaults(tmp_path: Path) -> None:
    store, _lib, _ = _seed_library(tmp_path)
    assert load_theme_mode(store) == "cyber_obsidian"
    assert appearance_path(store).is_file()

    result = reset_app_to_defaults(store)
    assert result.ok
    assert load_theme_mode(store) == "mica_dark"
    assert not appearance_path(store).exists()
    from semblon.media_grid import load_grid_density

    assert load_grid_density(store) == "comfortable"


def test_reset_removes_rebuildable_caches_and_figures(tmp_path: Path) -> None:
    store, _lib, _ = _seed_library(tmp_path)
    paths = resettable_paths(store)
    assert paths["visual_cache"].is_dir()
    assert paths["ann_index"].is_file()
    assert paths["review_html"].is_file()

    result = reset_app_to_defaults(store)
    assert result.ok
    assert not paths["visual_cache"].exists()
    assert not paths["ann_index"].exists()
    assert not paths["review_html"].exists()


def test_reset_clears_home_completion_meta_not_identity(tmp_path: Path) -> None:
    store, _lib, _ = _seed_library(tmp_path)
    result = reset_app_to_defaults(store)
    assert result.ok

    conn = sqlite3.connect(str(store))
    try:
        keys = {
            r[0]
            for r in conn.execute("SELECT key FROM schema_meta").fetchall()
        }
        assert "home_completion_kind" not in keys
        assert "home_completion_json" not in keys
        assert "home_completion_ack_run" not in keys
        assert "schema_version" in keys
        name = conn.execute(
            "SELECT display_name FROM persons WHERE person_id='p1'"
        ).fetchone()[0]
        assert name == "Alex"
        kind = conn.execute(
            "SELECT kind FROM decisions WHERE decision_id='d1'"
        ).fetchone()[0]
        assert kind == "name"
        region = conn.execute(
            "SELECT kind FROM observation_items WHERE item_id='r1'"
        ).fetchone()[0]
        assert region == "user_region"
    finally:
        conn.close()


def test_reset_does_not_delete_original_media(tmp_path: Path) -> None:
    store, lib_dir, probes = _seed_library(tmp_path)
    media_paths = list(probes.keys())
    result = reset_app_to_defaults(store)
    assert result.ok
    assert_media_untouched(media_paths, probe_bytes=probes)
    assert (lib_dir / "user_notes.txt").read_text(encoding="utf-8") == "do not delete me\n"


def test_reset_does_not_modify_library_folder_files(tmp_path: Path) -> None:
    store, lib_dir, probes = _seed_library(tmp_path)
    sentinel = lib_dir / "also_keep.bin"
    sentinel.write_bytes(b"SENTINEL")
    probes[sentinel] = sentinel.read_bytes()

    before = {p: p.stat().st_mtime_ns for p in probes}
    result = reset_app_to_defaults(store)
    assert result.ok
    assert_media_untouched(list(probes.keys()), probe_bytes=probes)
    for path, mtime in before.items():
        assert path.stat().st_mtime_ns == mtime


def test_reset_idempotent(tmp_path: Path) -> None:
    store, lib_dir, probes = _seed_library(tmp_path)
    first = reset_app_to_defaults(store)
    second = reset_app_to_defaults(store)
    assert first.ok and second.ok
    assert_media_untouched(list(probes.keys()), probe_bytes=probes)
    assert store.is_file()
    assert lib_dir.is_dir()


def test_reset_failure_does_not_claim_success_or_wipe_prefs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _lib, _ = _seed_library(tmp_path)
    assert appearance_path(store).is_file()

    def boom(path, *args, **kwargs):  # noqa: ANN001
        raise OSError("simulated cache clear failure")

    monkeypatch.setattr(shutil, "rmtree", boom)
    result = reset_app_to_defaults(store)
    assert not result.ok
    assert result.errors
    assert "could not finish" in result.message.lower() or "Reset could not" in result.message
    # Stage 2 prefs must not run after stage 1 failure.
    assert appearance_path(store).is_file()
    assert load_theme_mode(store) == "cyber_obsidian"


def test_reset_leaves_store_reopenable(tmp_path: Path) -> None:
    store, _lib, _ = _seed_library(tmp_path)
    assert reset_app_to_defaults(store).ok
    conn = sqlite3.connect(str(store))
    try:
        n = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        assert n == 1
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert ver == "4"
    finally:
        conn.close()


def test_reset_manifest_covers_media_boundary() -> None:
    rows = {name: (flag, why) for name, flag, why in RESET_MANIFEST}
    assert rows["Original photos and videos"][0] == "NO"
    assert rows["User library folders"][0] == "NO"
    assert rows["faces / persons / cluster_person"][0] == "NO"
    assert rows["decisions (name/merge/split/note/reject)"][0] == "NO"
    assert rows["appearance.json theme"][0] == "YES"
    assert rows["appearance.json grid_density"][0] == "YES"
    assert rows["appearance.json search_mode"][0] == "YES"
    assert rows["appearance.json library_filter"][0] == "YES"
    assert rows["appearance.json prefer_gpu"][0] == "YES"
    assert rows["visual_cache/ sidecars"][0] == "YES"


def test_home_reset_requires_confirmation_and_calls_service() -> None:
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._reset_app_to_defaults)
    fill = inspect.getsource(home_ui.HomeApp._fill_settings_body)
    assert "askyesno" in src
    assert "SETTINGS_RESET_CONFIRM" in src
    assert "reset_app_to_defaults" in src
    assert "self.app.busy" in src
    assert "SETTINGS_RESET_BUTTON" in fill
    assert "SETTINGS_RECOVERY" in fill


def test_cancel_path_is_no_op_when_declined() -> None:
    """Structural: early return before reset_app_to_defaults when confirm is False."""
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._reset_app_to_defaults)
    # Confirm gate precedes the service call.
    confirm_at = src.index("askyesno")
    call_at = src.index("reset_app_to_defaults(self.store)")
    assert confirm_at < call_at
    assert "return" in src[confirm_at:call_at]


def test_identity_authorization_strings_unchanged_by_reset_module() -> None:
    """Reset must not introduce a second compare/identity path or wipe store identity."""
    text = Path("semblon/app_reset.py").read_text(encoding="utf-8")
    assert "DBSCAN" not in text
    assert "Does not delete store.sqlite" in text or "PRESERVE" in text
    assert "resettable_paths" in text
    # Cleared paths are sidecars only — never the SQLite store file itself.
    assert 'skipped.append("store.sqlite' in text
