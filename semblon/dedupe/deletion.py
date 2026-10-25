"""Deletion planning, verification and audit (safety logic only — no file is removed here).

Ported in spirit from dedup ``engine/deletion.py``. Removal itself is injected (``remove``) so
Semblon keeps it behind explicit Tidy confirmation and the Recycle Bin. A target is deletable only
if, at execution time, it is still the same file (size/mtime), its full SHA-256 still equals the
group digest, and a *different* keeper copy still exists with that same digest.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .hashing import full_sha256
from .models import CancelToken, DuplicateGroup, DuplicateMember, ScanCancelled
from .path_policy import path_key

KEEP_STRATEGIES = ("first", "oldest", "newest", "shortest_path")


@dataclass(frozen=True, slots=True)
class PlannedGroup:
    sha256: str
    keep: DuplicateMember
    delete: tuple[DuplicateMember, ...]


@dataclass(frozen=True, slots=True)
class DeletionPlan:
    groups: tuple[PlannedGroup, ...]

    @property
    def target_count(self) -> int:
        return sum(len(g.delete) for g in self.groups)


@dataclass(slots=True)
class TargetVerification:
    path: str
    ok: bool
    reason: str = ""


@dataclass(slots=True)
class AuditRecord:
    when: str
    action: str  # verify | delete | skip | fail
    path: str
    sha256: str
    detail: str = ""


@dataclass(slots=True)
class PlanOutcome:
    deleted: list[str] = field(default_factory=list)
    skipped: list[TargetVerification] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    audit: list[AuditRecord] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_keeper(
    group: DuplicateGroup, strategy: str, keep_path: str | None
) -> DuplicateMember:
    members = list(group.members)
    if keep_path is not None:
        want = path_key(keep_path)
        for m in members:
            if path_key(m.path) == want:
                return m
        raise ValueError(f"keep path is not a member of the group: {keep_path}")
    if strategy == "first":
        return members[0]
    if strategy == "oldest":
        return min(members, key=lambda m: (m.mtime_ns, m.path.lower()))
    if strategy == "newest":
        return max(members, key=lambda m: (m.mtime_ns, m.path.lower()))
    if strategy == "shortest_path":
        return min(members, key=lambda m: (len(m.path), m.path.lower()))
    raise ValueError(f"unknown keep strategy: {strategy}")


def plan_deletions(
    groups: list[DuplicateGroup],
    *,
    strategy: str = "first",
    keep_paths: dict[str, str] | None = None,
) -> DeletionPlan:
    """One keeper per group (by ``keep_paths[sha256]`` or ``strategy``); everything else is a target."""
    keep_paths = keep_paths or {}
    planned: list[PlannedGroup] = []
    for g in groups:
        keeper = _pick_keeper(g, strategy, keep_paths.get(g.sha256))
        targets = tuple(m for m in g.members if path_key(m.path) != path_key(keeper.path))
        if targets:
            planned.append(PlannedGroup(g.sha256, keeper, targets))
    return DeletionPlan(tuple(planned))


def _verify_one(
    sha256: str,
    keeper: DuplicateMember,
    target: DuplicateMember,
    cancel: CancelToken | None,
) -> TargetVerification:
    if path_key(target.path) == path_key(keeper.path):
        return TargetVerification(target.path, False, "target is the keeper")
    try:
        st = os.stat(target.path)
    except OSError:
        return TargetVerification(target.path, False, "target missing")
    if not os.path.isfile(target.path) or os.path.islink(target.path):
        return TargetVerification(target.path, False, "target is not a regular file")
    if st.st_size != target.size or st.st_mtime_ns != target.mtime_ns:
        return TargetVerification(target.path, False, "target changed since scan")
    try:
        if not os.path.isfile(keeper.path):
            return TargetVerification(target.path, False, "keeper missing")
        if full_sha256(keeper.path, cancel=cancel) != sha256:
            return TargetVerification(target.path, False, "keeper content changed")
        if full_sha256(target.path, cancel=cancel) != sha256:
            return TargetVerification(target.path, False, "target content differs")
    except ScanCancelled:
        return TargetVerification(target.path, False, "cancelled")
    except OSError as exc:
        return TargetVerification(target.path, False, f"unreadable: {exc}")
    return TargetVerification(target.path, True)


def verify_plan(
    plan: DeletionPlan, cancel: CancelToken | None = None
) -> list[TargetVerification]:
    out: list[TargetVerification] = []
    for g in plan.groups:
        for t in g.delete:
            out.append(_verify_one(g.sha256, g.keep, t, cancel))
    return out


def execute_plan(
    plan: DeletionPlan,
    remove: Callable[[str], None],
    *,
    confirmed: bool,
    cancel: CancelToken | None = None,
) -> PlanOutcome:
    """Remove verified targets through ``remove`` (e.g. Recycle Bin). Refuses without ``confirmed``.

    Each target is re-verified immediately before removal; a failed verification skips that target
    and never the whole plan. The keeper is never passed to ``remove``.
    """
    if not confirmed:
        raise PermissionError("deletion requires explicit confirmation")
    outcome = PlanOutcome()
    for g in plan.groups:
        keeper_key = path_key(g.keep.path)
        for t in g.delete:
            if cancel is not None and cancel.cancelled:
                return outcome
            if path_key(t.path) == keeper_key:
                outcome.audit.append(AuditRecord(_now(), "skip", t.path, g.sha256, "is keeper"))
                continue
            v = _verify_one(g.sha256, g.keep, t, cancel)
            outcome.audit.append(
                AuditRecord(_now(), "verify", t.path, g.sha256, "ok" if v.ok else v.reason)
            )
            if not v.ok:
                outcome.skipped.append(v)
                continue
            try:
                remove(t.path)
            except Exception as exc:  # noqa: BLE001
                outcome.failed.append((t.path, str(exc)))
                outcome.audit.append(AuditRecord(_now(), "fail", t.path, g.sha256, str(exc)))
                continue
            outcome.deleted.append(t.path)
            outcome.audit.append(AuditRecord(_now(), "delete", t.path, g.sha256))
    return outcome
