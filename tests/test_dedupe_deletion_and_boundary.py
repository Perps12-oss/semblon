"""Dedupe deletion safety (planning, verification, confirmation) and import boundary."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

import semblon.dedupe as dedupe_pkg
from semblon.dedupe import (
    DuplicateGroup,
    DuplicateMember,
    execute_plan,
    plan_deletions,
    scan_exact,
    verify_plan,
)


def _dupes(tmp_path: Path, n: int = 3, payload: bytes = b"same-bytes"):
    files = []
    for i in range(n):
        p = tmp_path / f"f{i}.jpg"
        p.write_bytes(payload)
        os.utime(p, ns=(1_000_000_000 * (i + 1),) * 2)
        files.append(p)
    return scan_exact(files).groups


def test_plan_keep_never_in_delete_list(tmp_path):
    groups = _dupes(tmp_path)
    plan = plan_deletions(groups, strategy="first")
    g = plan.groups[0]
    assert g.keep.path not in {m.path for m in g.delete}
    assert len(g.delete) == 2 and plan.target_count == 2


def test_plan_strategies_and_explicit_keep(tmp_path):
    groups = _dupes(tmp_path)
    paths = {Path(m.path).name: m.path for m in groups[0].members}
    assert Path(plan_deletions(groups, strategy="oldest").groups[0].keep.path).name == "f0.jpg"
    assert Path(plan_deletions(groups, strategy="newest").groups[0].keep.path).name == "f2.jpg"
    plan = plan_deletions(groups, keep_paths={groups[0].sha256: paths["f1.jpg"]})
    assert Path(plan.groups[0].keep.path).name == "f1.jpg"
    with pytest.raises(ValueError):
        plan_deletions(groups, keep_paths={groups[0].sha256: "/not/a/member"})
    with pytest.raises(ValueError):
        plan_deletions(groups, strategy="bogus")


def test_execute_requires_confirmation_and_removes_only_targets(tmp_path):
    groups = _dupes(tmp_path)
    plan = plan_deletions(groups)
    removed: list[str] = []
    with pytest.raises(PermissionError):
        execute_plan(plan, removed.append, confirmed=False)
    assert removed == []
    out = execute_plan(plan, removed.append, confirmed=True)
    assert out.deleted == removed and len(removed) == 2
    assert plan.groups[0].keep.path not in removed
    assert {a.action for a in out.audit} >= {"verify", "delete"}


def test_modified_target_is_skipped(tmp_path):
    groups = _dupes(tmp_path)
    plan = plan_deletions(groups)
    victim = Path(plan.groups[0].delete[0].path)
    victim.write_bytes(b"same-bytes")  # same content, but mtime moved
    os.utime(victim, ns=(9_000_000_000, 9_000_000_000))
    v = {x.path: x for x in verify_plan(plan)}
    assert not v[str(victim)].ok and "changed" in v[str(victim)].reason
    removed: list[str] = []
    out = execute_plan(plan, removed.append, confirmed=True)
    assert str(victim) not in removed and len(out.skipped) == 1


def test_content_change_with_same_size_and_mtime_is_caught(tmp_path):
    groups = _dupes(tmp_path, n=2)
    plan = plan_deletions(groups)
    t = Path(plan.groups[0].delete[0].path)
    st = t.stat()
    t.write_bytes(b"SAME-BYTES")  # same length
    os.utime(t, ns=(st.st_atime_ns, st.st_mtime_ns))
    (v,) = verify_plan(plan)
    assert not v.ok and v.reason == "target content differs"


def test_missing_keeper_blocks_deletion(tmp_path):
    groups = _dupes(tmp_path, n=2)
    plan = plan_deletions(groups)
    Path(plan.groups[0].keep.path).unlink()
    (v,) = verify_plan(plan)
    assert not v.ok and v.reason == "keeper missing"


def test_remove_failure_is_reported_not_fatal(tmp_path):
    plan = plan_deletions(_dupes(tmp_path))

    def boom(_p: str) -> None:
        raise OSError("locked")

    out = execute_plan(plan, boom, confirmed=True)
    assert out.deleted == [] and len(out.failed) == 2


def test_forged_plan_with_keeper_as_target_is_ignored(tmp_path):
    from semblon.dedupe.deletion import DeletionPlan, PlannedGroup

    g = _dupes(tmp_path, n=2)[0]
    keep, other = g.members
    forged = DeletionPlan((PlannedGroup(g.sha256, keep, (keep, other)),))
    removed: list[str] = []
    execute_plan(forged, removed.append, confirmed=True)
    assert removed == [other.path]


def test_group_type_rejects_partial_digest():
    with pytest.raises(ValueError):
        DuplicateGroup("deadbeef", (DuplicateMember("a", 1, 0), DuplicateMember("b", 1, 0)))


# ── import boundary ──────────────────────────────────────────────────────
FORBIDDEN_PREFIXES = (
    "semblon",  # only semblon.dedupe.* is allowed (checked below)
    "PySide6",
    "PyQt5",
    "PyQt6",
    "tkinter",
    "customtkinter",
    "cv2",
    "numpy",
    "onnxruntime",
    "insightface",
    "sqlite3",
)


def _imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, int]] = []
    pkg = "semblon.dedupe"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import stays inside semblon.dedupe
                continue
            out.append((node.module or "", node.lineno))
    return out


def test_dedupe_import_boundary():
    root = Path(dedupe_pkg.__file__).parent
    offenders = []
    for py in sorted(root.glob("*.py")):
        for mod, line in _imports(py):
            top = mod.split(".")[0]
            if mod == "semblon.dedupe" or mod.startswith("semblon.dedupe."):
                continue
            if top in {p.split(".")[0] for p in FORBIDDEN_PREFIXES}:
                offenders.append(f"{py.name}:{line} imports {mod}")
    assert offenders == []


def test_dedupe_import_does_not_load_forbidden_modules():
    import subprocess
    import sys

    code = (
        "import sys, semblon.dedupe\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "{'PySide6','tkinter','cv2','sqlite3'} or m in "
        "{'semblon.store','semblon.engine','semblon.ingest','semblon.duplicates'}]\n"
        "print(','.join(sorted(bad)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == ""
