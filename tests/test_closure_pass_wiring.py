"""Closure pass: coded-but-not-wired capabilities become product-reachable."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from semblon.gui_registry import FeatureRegistry
from semblon.home_shell import probe_model_overrides
from semblon.product_features import INSPECTOR_VERB_SPECS, build_product_registry
from semblon.product_surface import VERB_LABEL_NOTE
from semblon.store import init_db
from semblon.user_region import name_user_region, persist_user_region


def test_registry_exposes_closure_commands():
    reg = build_product_registry()
    ids = {c.id for c in reg.commands()}
    assert "lens.ask_selection" in ids
    assert "lens.name_region" in ids
    assert "compare.exit" in ids
    assert "inspector.verb.note" in ids
    assert "library.duplicates" in ids
    ask = reg.get_command("lens.ask_selection")
    assert ask is not None
    assert ask.label == "Ask about this selection"
    note_ids = {spec[1] for spec in INSPECTOR_VERB_SPECS}
    assert "inspector.verb.note" in note_ids
    assert VERB_LABEL_NOTE == "Note…"


def test_compare_exit_is_inspector_surface_and_gated():
    reg = build_product_registry()
    cmd = reg.get_command("compare.exit")
    assert cmd is not None
    assert "inspector" in cmd.surfaces
    assert "palette" in cmd.surfaces

    class _Cmp:
        active = False

    class _Host:
        _compare = _Cmp()

    host = _Host()
    assert cmd.is_available(host) is False
    host._compare.active = True
    assert cmd.is_available(host) is True


def test_home_packs_leave_compare_via_registry_not_skip():
    import semblon.home_ui as home_ui

    init_src = inspect.getsource(home_ui.HomeApp.__init__)
    # compare.exit must NOT be in the hardcoded skip set.
    skip_chunk = init_src.split("if cmd.id in _verb_ids or cmd.id in {")[1].split("}:")[0]
    assert "compare.exit" not in skip_chunk
    sync = inspect.getsource(home_ui.HomeApp._sync_discovery_actions)
    assert "_sync_registry_inspector_commands" in sync


def test_ask_selection_and_name_region_methods_exist():
    import semblon.home_ui as home_ui

    assert hasattr(home_ui.HomeApp, "_ask_about_selection")
    assert hasattr(home_ui.HomeApp, "_name_saved_region")
    assert hasattr(home_ui.HomeApp, "_selection_query_rect")
    ask_src = inspect.getsource(home_ui.HomeApp._ask_about_selection)
    assert "query_media" in ask_src
    assert "run_lens_query" not in ask_src
    assert "dict(rect)" in ask_src
    # Must stay distinct from Find Similar stack.
    assert "remember_selection" not in ask_src
    assert "remember_and_find" not in ask_src
    name_src = inspect.getsource(home_ui.HomeApp._name_saved_region)
    assert "name_region" in name_src
    assert "not a person" in name_src.lower() or "not a person" in name_src


def test_name_region_persists_without_identity(tmp_path: Path):
    from semblon.store import connect

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',200,100,0,1)")
    conn.commit()
    conn.close()
    saved = persist_user_region(store, media_id="m1", x=1, y=2, w=10, h=12, run_id="r1")
    persons_before = saved["persons"]
    named = name_user_region(store, saved["item_id"], "old camera")
    assert named["named"] == "old camera"
    assert named["entity"] is False
    assert named["persons"] == persons_before == 0
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    conn.close()


def test_inspector_note_uses_apply_note_path():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._inspector_note)
    assert "apply_note" in src
    assert "simpledialog" in src
    assert "from semblon.review_ui import ReviewUiError, apply_note" in src


def test_sam2_probe_uses_real_runtime_api():
    src = inspect.getsource(probe_model_overrides)
    assert "sam2_ready" not in src
    assert "probe_sam2" in src
    assert "SAM2_AVAILABLE" in src or "SAM2_READY" in src
    # Must not force-load weights during honesty probe.
    assert "attempt_load=False" in src
    probed = probe_model_overrides()
    assert isinstance(probed, dict)


def test_ask_selection_availability_requires_rect():
    from semblon.product_features import (
        _ask_selection_available,
        _name_region_available,
    )

    class _Host:
        _last_user_region_id = None

        def _selection_query_rect(self):
            return None

    host = _Host()
    assert _ask_selection_available(host) is False
    assert _name_region_available(host) is False
    host._selection_query_rect = lambda: {"x": 0, "y": 0, "w": 4, "h": 4}
    assert _ask_selection_available(host) is True
    host._last_user_region_id = "item1"
    assert _name_region_available(host) is True


def test_product_exposure_marks_continuous_watch_cli_only():
    from semblon.product_exposure import GUI_PATHS

    watch_rows = [r for r in GUI_PATHS if "watch" in r[0].lower() or "Watch" in r[2]]
    assert watch_rows
    continuous = [r for r in watch_rows if r[1] == "CLI"]
    assert continuous
    assert any("one-shot" in r[2] or "semblon watch" in r[2] for r in continuous)


def test_duplicates_command_still_registered_after_closure():
    reg = build_product_registry()
    cmd = reg.get_command("library.duplicates")
    assert cmd is not None
    assert cmd.label == "Find Duplicates"
    assert "inspector" in cmd.surfaces


def test_pause_resume_cancel_use_job_engine_contracts():
    """Busy ingest controls call existing JobEngine pause/cancel — no second path."""
    import semblon.home_ui as home_ui

    pause_src = inspect.getsource(home_ui.HomeApp._request_pause)
    cancel_src = inspect.getsource(home_ui.HomeApp._request_cancel)
    toggle_src = inspect.getsource(home_ui.HomeApp._toggle_pause_resume)
    assert "pause_job" in pause_src
    assert "cancel_job" in cancel_src
    assert "_request_pause" in toggle_src
    assert "_resume" in toggle_src
    # Cancel must not delete media / unlink files.
    assert "unlink" not in cancel_src
    assert "delete" not in cancel_src.lower()


def test_keep_reject_remain_session_only_and_non_destructive():
    import semblon.home_ui as home_ui

    enter = inspect.getsource(home_ui.HomeApp._enter_compare)
    assert "session only" in enter.lower()
    decide = inspect.getsource(home_ui.HomeApp._compare_decide)
    assert "unlink" not in decide
    assert "os.remove" not in decide
    assert "DELETE FROM" not in decide


def test_note_verb_enabled_with_face_selection():
    from semblon.inspector_verbs import inspector_verb_states

    st = inspector_verb_states(
        [{"kind": "face", "face_id": "f1"}],
        run_id="r1",
    )
    assert st["note"]["enabled"] is True
