"""P0 Source 1 — runtime SQLite instrumentation.

Installs set_authorizer + set_trace_callback on every sqlite3.connect and on
semblon.store.connect / connect_readonly when SEMBLON_P0_SQL_TRACE=1.

Captures: SQL identity, operation, tables, connection id, caller context,
parameter count and Python types — never parameter values or archive content.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_INSTALLED = False
_LOCK = threading.Lock()
_EVENTS: list[dict] = []
_CONN_META: dict[int, dict] = {}
_AUTHORIZER_COUNTS: Counter = Counter()
_SKIP_FRAMES = {
    "sql_runtime_trace.py",
    "threading.py",
    "contextlib.py",
}


@dataclass
class TraceSummary:
    event_count: int = 0
    connections: int = 0
    by_op: dict[str, int] = field(default_factory=dict)
    by_table: dict[str, int] = field(default_factory=dict)
    by_caller: dict[str, int] = field(default_factory=dict)
    authorizer_actions: dict[str, int] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0


def _caller_context(depth: int = 12) -> dict:
    frames = traceback.extract_stack(limit=depth + 8)
    useful = []
    for frame in frames[:-1]:
        name = Path(frame.filename).name
        if name in _SKIP_FRAMES:
            continue
        if "site-packages" in frame.filename.replace("\\", "/"):
            continue
        useful.append(
            {
                "file": frame.filename.replace("\\", "/"),
                "line": frame.lineno,
                "func": frame.name,
            }
        )
    top = useful[-1] if useful else None
    return {
        "top": top,
        "stack": useful[-6:],
    }


def _sql_op(sql: str | None) -> str:
    if not sql:
        return "EMPTY"
    token = sql.lstrip().split(None, 1)[0].upper() if sql.lstrip() else "EMPTY"
    return token


def _tables_from_sql(sql: str | None) -> list[str]:
    if not sql:
        return []
    import re

    found = re.findall(
        r"\b(?:INTO|UPDATE|FROM|JOIN|TABLE(?: IF NOT EXISTS)?)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        sql,
        flags=re.IGNORECASE,
    )
    return sorted({name.lower() for name in found})


def _param_shape(params: Any) -> dict:
    if params is None:
        return {"count": 0, "kinds": []}
    if isinstance(params, dict):
        kinds = sorted({type(v).__name__ for v in params.values()})
        return {"count": len(params), "kinds": kinds, "binding": "named"}
    if isinstance(params, (tuple, list)):
        kinds = sorted({type(v).__name__ for v in params})
        return {"count": len(params), "kinds": kinds, "binding": "positional"}
    return {"count": 1, "kinds": [type(params).__name__], "binding": "scalar"}


def _record(event: dict) -> None:
    with _LOCK:
        _EVENTS.append(event)


def _authorizer(action_code, arg1, arg2, dbname, source):  # noqa: ANN001
    # Always allow. This is observation only.
    name = {
        sqlite3.SQLITE_CREATE_INDEX: "CREATE_INDEX",
        sqlite3.SQLITE_CREATE_TABLE: "CREATE_TABLE",
        sqlite3.SQLITE_CREATE_TEMP_INDEX: "CREATE_TEMP_INDEX",
        sqlite3.SQLITE_CREATE_TEMP_TABLE: "CREATE_TEMP_TABLE",
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER: "CREATE_TEMP_TRIGGER",
        sqlite3.SQLITE_CREATE_TEMP_VIEW: "CREATE_TEMP_VIEW",
        sqlite3.SQLITE_CREATE_TRIGGER: "CREATE_TRIGGER",
        sqlite3.SQLITE_CREATE_VIEW: "CREATE_VIEW",
        sqlite3.SQLITE_DELETE: "DELETE",
        sqlite3.SQLITE_DROP_INDEX: "DROP_INDEX",
        sqlite3.SQLITE_DROP_TABLE: "DROP_TABLE",
        sqlite3.SQLITE_DROP_TEMP_INDEX: "DROP_TEMP_INDEX",
        sqlite3.SQLITE_DROP_TEMP_TABLE: "DROP_TEMP_TABLE",
        sqlite3.SQLITE_DROP_TEMP_TRIGGER: "DROP_TEMP_TRIGGER",
        sqlite3.SQLITE_DROP_TEMP_VIEW: "DROP_TEMP_VIEW",
        sqlite3.SQLITE_DROP_TRIGGER: "DROP_TRIGGER",
        sqlite3.SQLITE_DROP_VIEW: "DROP_VIEW",
        sqlite3.SQLITE_INSERT: "INSERT",
        sqlite3.SQLITE_PRAGMA: "PRAGMA",
        sqlite3.SQLITE_READ: "READ",
        sqlite3.SQLITE_SELECT: "SELECT",
        sqlite3.SQLITE_TRANSACTION: "TRANSACTION",
        sqlite3.SQLITE_UPDATE: "UPDATE",
        sqlite3.SQLITE_ATTACH: "ATTACH",
        sqlite3.SQLITE_DETACH: "DETACH",
        sqlite3.SQLITE_ALTER_TABLE: "ALTER_TABLE",
        sqlite3.SQLITE_REINDEX: "REINDEX",
        sqlite3.SQLITE_ANALYZE: "ANALYZE",
        sqlite3.SQLITE_CREATE_VTABLE: "CREATE_VTABLE",
        sqlite3.SQLITE_DROP_VTABLE: "DROP_VTABLE",
        sqlite3.SQLITE_FUNCTION: "FUNCTION",
        sqlite3.SQLITE_SAVEPOINT: "SAVEPOINT",
        sqlite3.SQLITE_RECURSIVE: "RECURSIVE",
    }.get(action_code, f"ACTION_{action_code}")
    with _LOCK:
        _AUTHORIZER_COUNTS[name] += 1
    # Record table/column identity only — never values.
    if name in {"INSERT", "UPDATE", "DELETE", "READ", "SELECT"} and arg1:
        _record(
            {
                "kind": "authorizer",
                "action": name,
                "table": arg1,
                "column": arg2,
                "dbname": dbname,
                "source": source,
                "caller": _caller_context(),
                "t": time.time(),
            }
        )
    return sqlite3.SQLITE_OK


class TracedConnection(sqlite3.Connection):
    """Connection subclass. execute cannot be monkeypatched on CPython 3.12+."""

    _semblon_origin: str = "sqlite3.connect"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cid = id(self)
        with _LOCK:
            _CONN_META[cid] = {
                "origin": getattr(self, "_semblon_origin", "sqlite3.connect"),
                "opened_at": time.time(),
            }

        def _trace(statement: str) -> None:
            preview = " ".join((statement or "").split())
            if len(preview) > 180:
                preview = preview[:177] + "..."
            _record(
                {
                    "kind": "trace",
                    "conn_id": cid,
                    "origin": getattr(self, "_semblon_origin", "sqlite3.connect"),
                    "op": _sql_op(statement),
                    "tables": _tables_from_sql(statement),
                    "statement_preview": preview,
                    "caller": _caller_context(),
                    "t": time.time(),
                }
            )

        try:
            self.set_authorizer(_authorizer)
        except Exception:
            pass
        try:
            self.set_trace_callback(_trace)
        except Exception:
            pass

    def execute(self, sql, parameters=()):  # noqa: ANN001
        self._log_exec("execute", sql, parameters)
        return super().execute(sql, parameters)

    def executemany(self, sql, parameters):  # noqa: ANN001
        # Shape only: first row types if present, else count unknown.
        sample = None
        try:
            iterator = iter(parameters)
            first = next(iterator, None)
            sample = first
            if first is None:
                parameters = []
            else:
                def _chain():
                    yield first
                    yield from iterator

                parameters = _chain()
        except TypeError:
            sample = parameters
        self._log_exec("executemany", sql, sample)
        return super().executemany(sql, parameters)

    def executescript(self, sql_script: str):
        preview = " ".join(str(sql_script).split())
        if len(preview) > 180:
            preview = preview[:177] + "..."
        _record(
            {
                "kind": "executescript",
                "conn_id": id(self),
                "origin": getattr(self, "_semblon_origin", "sqlite3.connect"),
                "op": "SCRIPT",
                "tables": _tables_from_sql(str(sql_script)),
                "statement_preview": preview,
                "param_shape": {"count": 0, "kinds": []},
                "caller": _caller_context(),
                "t": time.time(),
            }
        )
        return super().executescript(sql_script)

    def _log_exec(self, method: str, sql, parameters) -> None:  # noqa: ANN001
        shape = _param_shape(parameters)
        preview = " ".join(str(sql).split())
        if len(preview) > 180:
            preview = preview[:177] + "..."
        _record(
            {
                "kind": "execute",
                "method": method,
                "conn_id": id(self),
                "origin": getattr(self, "_semblon_origin", "sqlite3.connect"),
                "op": _sql_op(str(sql)),
                "tables": _tables_from_sql(str(sql)),
                "statement_preview": preview,
                "param_shape": shape,
                "caller": _caller_context(),
                "t": time.time(),
            }
        )


def _instrument_connection(conn: sqlite3.Connection, *, origin: str) -> sqlite3.Connection:
    """Attach authorizer/trace when factory was not used (e.g. already-open conn)."""
    cid = id(conn)
    with _LOCK:
        _CONN_META[cid] = {"origin": origin, "opened_at": time.time()}

    def _trace(statement: str) -> None:
        preview = " ".join((statement or "").split())
        if len(preview) > 180:
            preview = preview[:177] + "..."
        _record(
            {
                "kind": "trace",
                "conn_id": cid,
                "origin": origin,
                "op": _sql_op(statement),
                "tables": _tables_from_sql(statement),
                "statement_preview": preview,
                "caller": _caller_context(),
                "t": time.time(),
            }
        )

    try:
        conn.set_authorizer(_authorizer)
    except Exception:
        pass
    try:
        conn.set_trace_callback(_trace)
    except Exception:
        pass
    return conn


def install() -> bool:
    """Patch sqlite3.connect and semblon.store connect helpers. Idempotent."""
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return False
        _INSTALLED = True
        _EVENTS.clear()
        _CONN_META.clear()
        _AUTHORIZER_COUNTS.clear()

    import sqlite3 as _sqlite3

    original_connect = _sqlite3.connect

    def traced_connect(*args, **kwargs):
        if "factory" not in kwargs:
            kwargs["factory"] = TracedConnection
        conn = original_connect(*args, **kwargs)
        if isinstance(conn, TracedConnection):
            conn._semblon_origin = "sqlite3.connect"
        else:
            _instrument_connection(conn, origin="sqlite3.connect")
        return conn

    _sqlite3.connect = traced_connect  # type: ignore[assignment]

    try:
        from semblon import store as store_mod

        def traced_store_connect(path):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = original_connect(str(path), factory=TracedConnection)
            conn._semblon_origin = "store.connect"
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = _sqlite3.Row
            return conn

        def traced_ro(store):
            path = Path(store).expanduser().resolve()
            conn = original_connect(path.as_uri() + "?mode=ro", uri=True, factory=TracedConnection)
            conn._semblon_origin = "store.connect_readonly"
            conn.row_factory = _sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            return conn

        store_mod.connect = traced_store_connect  # type: ignore[assignment]
        store_mod.connect_readonly = traced_ro  # type: ignore[assignment]
    except Exception:
        pass
    return True


def enabled() -> bool:
    return os.environ.get("SEMBLON_P0_SQL_TRACE", "").strip() in {"1", "true", "yes"}


def summary() -> TraceSummary:
    with _LOCK:
        events = list(_EVENTS)
        conns = dict(_CONN_META)
        auth = dict(_AUTHORIZER_COUNTS)
    by_op: Counter = Counter()
    by_table: Counter = Counter()
    by_caller: Counter = Counter()
    times = [e.get("t") for e in events if e.get("t")]
    for event in events:
        if event.get("kind") == "authorizer":
            continue
        by_op[str(event.get("op") or "?")] += 1
        for table in event.get("tables") or []:
            by_table[str(table)] += 1
        top = (event.get("caller") or {}).get("top") or {}
        label = f"{Path(str(top.get('file') or '?')).name}:{top.get('func') or '?'}"
        by_caller[label] += 1
    return TraceSummary(
        event_count=len(events),
        connections=len(conns),
        by_op=dict(by_op.most_common()),
        by_table=dict(by_table.most_common()),
        by_caller=dict(by_caller.most_common(40)),
        authorizer_actions=auth,
        started_at=min(times) if times else 0.0,
        finished_at=max(times) if times else 0.0,
    )


def dump(path: Path) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        events = list(_EVENTS)
        conns = {str(k): v for k, v in _CONN_META.items()}
    payload = {
        "summary": asdict(summary()),
        "connections": conns,
        "events": events,
        "note": "parameter values intentionally omitted; archive content never logged",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload["summary"]


def reset() -> None:
    with _LOCK:
        _EVENTS.clear()
        _CONN_META.clear()
        _AUTHORIZER_COUNTS.clear()
