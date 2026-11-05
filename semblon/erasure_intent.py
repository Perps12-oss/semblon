"""ErasureIntent — caller type plus connection-local DB enforcement helpers.

The dataclass alone is not enforcement. Writable connections register
``semblon_erasure_ok``; BEFORE DELETE triggers call it and fail closed when
intent is absent, invalid, or insufficient for the row.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

HUMAN_DECISION_KINDS = frozenset({"name", "reject", "merge", "split", "note"})

_TLS = threading.local()


class ErasureAuthorizationError(RuntimeError):
    """Raised when a protected delete runs without sufficient ErasureIntent."""


@dataclass(frozen=True)
class ErasureIntent:
    """User-authorised erasure request. Not proof by itself — DB guard checks it."""

    requestor: str
    scope: str
    reason: str
    authorized_by: str
    person_id: str | None = None
    face_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        scope = str(self.scope or "").strip().lower()
        if scope not in {"person", "library"}:
            raise ValueError(f"unsupported erasure scope: {self.scope!r}")
        object.__setattr__(self, "scope", scope)
        requestor = str(self.requestor or "").strip()
        reason = str(self.reason or "").strip()
        authorized_by = str(self.authorized_by or "").strip()
        if not requestor or not reason or not authorized_by:
            raise ValueError("requestor, reason, and authorized_by are required")
        object.__setattr__(self, "requestor", requestor)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "authorized_by", authorized_by)
        if scope == "person":
            person_id = str(self.person_id or "").strip()
            if not person_id:
                raise ValueError("person_id is required for scope=person")
            object.__setattr__(self, "person_id", person_id)
            faces = frozenset(str(f).strip() for f in self.face_ids if str(f).strip())
            object.__setattr__(self, "face_ids", faces)
        else:
            object.__setattr__(self, "person_id", None)
            object.__setattr__(self, "face_ids", frozenset())


def current_erasure_intent() -> ErasureIntent | None:
    return getattr(_TLS, "intent", None)


@contextmanager
def erasure_authorized(intent: ErasureIntent) -> Iterator[ErasureIntent]:
    """Activate intent for this thread while protected deletes run."""
    if not isinstance(intent, ErasureIntent):
        raise TypeError("ErasureIntent required")
    previous = getattr(_TLS, "intent", None)
    _TLS.intent = intent
    try:
        yield intent
    finally:
        _TLS.intent = previous


def _sql_erasure_ok(
    table: str | None,
    kind: str | None,
    person_id: str | None,
    face_id: str | None,
) -> int:
    """SQLite callback: 1 allow, 0 deny. Never trust caller convention alone."""
    intent = current_erasure_intent()
    if intent is None:
        return 0
    table_name = str(table or "").strip().lower()
    if intent.scope == "library":
        return 1
    if intent.scope != "person" or not intent.person_id:
        return 0
    pid = str(person_id or "").strip() or None
    fid = str(face_id or "").strip() or None
    if table_name == "persons":
        return 1 if pid == intent.person_id else 0
    if table_name == "faces":
        return 1 if pid == intent.person_id else 0
    if table_name == "decisions":
        if pid and pid == intent.person_id:
            return 1
        if fid and fid in intent.face_ids:
            return 1
        return 0
    return 0


def install_erasure_guard(conn: sqlite3.Connection) -> None:
    """Register the fail-closed erasure check on a writable connection."""
    conn.create_function("semblon_erasure_ok", 4, _sql_erasure_ok, deterministic=False)
