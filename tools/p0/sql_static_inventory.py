"""P0 Source 2 — static SQLite access inventory.

Maps connect sites and SQL execution sites to tables/columns when the SQL is
literal. Dynamic SQL is classified as dynamic. Never logs parameter values.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("semblon", "tools")
SKIP_PARTS = {".venv", "__pycache__", ".pytest-tmp", "artifacts", "node_modules"}

CONNECT_NAMES = {
    "connect",
    "connect_readonly",
    "sqlite3.connect",
}
EXEC_ATTRS = {"execute", "executemany", "executescript"}
HELPER_FUNCS = {"exec_in_chunks", "rows_in_chunks"}

TABLE_RE = re.compile(
    r"\b(?:INTO|UPDATE|FROM|JOIN|TABLE(?: IF NOT EXISTS)?)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
OP_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|SELECT|CREATE|DROP|ALTER|PRAGMA|ATTACH|DETACH|BEGIN|COMMIT|ROLLBACK|REPLACE)\b",
    re.IGNORECASE,
)


def _skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_str(node.left)
        right = _literal_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = []
        cur: ast.AST = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _classify_sql(sql: str | None) -> dict:
    if sql is None:
        return {
            "sql_kind": "dynamic",
            "ops": [],
            "tables": [],
            "statement_preview": None,
        }
    ops = sorted({m.group(1).upper() for m in OP_RE.finditer(sql)})
    tables = sorted({m.group(1).lower() for m in TABLE_RE.finditer(sql)})
    preview = " ".join(sql.split())
    if len(preview) > 160:
        preview = preview[:157] + "..."
    return {
        "sql_kind": "literal",
        "ops": ops,
        "tables": tables,
        "statement_preview": preview,
    }


class InventoryVisitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.rel = _rel(path)
        self.stack: list[str] = []
        self.connects: list[dict] = []
        self.execs: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        caller = ".".join(self.stack) if self.stack else "<module>"
        base = {
            "file": self.rel,
            "line": node.lineno,
            "caller": caller,
            "call": name,
        }
        if name in {"connect", "connect_readonly"} or name.endswith(".connect"):
            self.connects.append({**base, "kind": "connect"})
        elif isinstance(node.func, ast.Attribute) and node.func.attr in EXEC_ATTRS:
            sql = _literal_str(node.args[0]) if node.args else None
            self.execs.append({**base, "kind": "exec", **_classify_sql(sql)})
        elif name.split(".")[-1] in HELPER_FUNCS:
            sql = _literal_str(node.args[1]) if len(node.args) > 1 else None
            # exec_in_chunks(conn, sql_prefix, ...)
            if name.split(".")[-1] == "exec_in_chunks" and len(node.args) > 1:
                sql = _literal_str(node.args[1])
            if name.split(".")[-1] == "rows_in_chunks" and len(node.args) > 1:
                sql = _literal_str(node.args[1])
            self.execs.append({**base, "kind": "helper", **_classify_sql(sql)})
        self.generic_visit(node)


def scan() -> dict:
    connects: list[dict] = []
    execs: list[dict] = []
    parse_errors: list[dict] = []
    for folder in SCAN_DIRS:
        root = ROOT / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if _skip(path):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                parse_errors.append({"file": _rel(path), "error": str(exc)})
                continue
            visitor = InventoryVisitor(path)
            visitor.visit(tree)
            connects.extend(visitor.connects)
            execs.extend(visitor.execs)

    by_table: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_file: dict[str, int] = defaultdict(int)
    dynamic = 0
    for row in execs:
        by_file[row["file"]] += 1
        if row["sql_kind"] == "dynamic":
            dynamic += 1
            continue
        for table in row["tables"]:
            for op in row["ops"] or ["UNKNOWN"]:
                by_table[table][op] += 1

    writers = []
    readers = []
    for row in execs:
        ops = set(row.get("ops") or [])
        write_ops = ops & {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"}
        read_ops = ops & {"SELECT"}
        if write_ops:
            writers.append(row)
        if read_ops or (not write_ops and row["sql_kind"] == "literal"):
            if read_ops:
                readers.append(row)

    return {
        "root": str(ROOT),
        "connect_sites": connects,
        "connect_count": len(connects),
        "exec_sites": execs,
        "exec_count": len(execs),
        "dynamic_sql_count": dynamic,
        "writers": writers,
        "readers": readers,
        "writer_count": len(writers),
        "reader_count": len(readers),
        "by_table": {k: dict(v) for k, v in sorted(by_table.items())},
        "by_file": dict(sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0]))),
        "parse_errors": parse_errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "p0" / "sql_static_inventory.json",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    report = scan()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.summary:
        print(f"connect_sites={report['connect_count']}")
        print(f"exec_sites={report['exec_count']}")
        print(f"dynamic_sql={report['dynamic_sql_count']}")
        print(f"writers={report['writer_count']} readers={report['reader_count']}")
        print(f"tables={len(report['by_table'])}")
        print(f"out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
