"""Reconcile static inventory vs runtime SQL trace. Writes a summary JSON."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    static = json.loads((ROOT / "artifacts/p0/sql_static_inventory.json").read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "artifacts/p0/sql_runtime_trace.json").read_text(encoding="utf-8"))
    smoke = json.loads((ROOT / "artifacts/p0/workflow_smoke.json").read_text(encoding="utf-8"))

    rt_tables: set[str] = set()
    rt_write_tables: Counter = Counter()
    rt_read_tables: Counter = Counter()
    callers_by_table: dict[str, Counter] = defaultdict(Counter)
    for event in runtime["events"]:
        if event.get("kind") not in {"execute", "trace", "executescript"}:
            continue
        op = event.get("op")
        for table in event.get("tables") or []:
            rt_tables.add(table)
            if op in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "SCRIPT"}:
                rt_write_tables[table] += 1
            if op == "SELECT":
                rt_read_tables[table] += 1
            top = (event.get("caller") or {}).get("top") or {}
            label = f"{Path(str(top.get('file') or '?')).name}:{top.get('func')}"
            callers_by_table[table][label] += 1

    static_tables = set(static["by_table"])
    id_tables = {
        "faces",
        "embeddings",
        "decisions",
        "persons",
        "clusters",
        "cluster_person",
        "runs",
        "observations",
        "observation_items",
        "eval_pairs",
        "eval_sets",
        "work_items",
        "category_coverage",
        "media",
    }
    identity = {}
    for table in sorted(id_tables):
        identity[table] = {
            "runtime_writes": rt_write_tables[table],
            "runtime_reads": rt_read_tables[table],
            "top_callers": callers_by_table[table].most_common(8),
            "static_ops": static["by_table"].get(table, {}),
        }

    # Static writers not observed in focused runtime — classify later in docs.
    static_write_files = sorted(
        {
            row["file"]
            for row in static["writers"]
            if any(t in id_tables for t in row.get("tables") or [])
        }
    )
    runtime_files = {
        Path(str(((e.get("caller") or {}).get("top") or {}).get("file") or "")).name
        for e in runtime["events"]
        if e.get("kind") in {"execute", "trace", "executescript"}
    }

    out = {
        "baseline_note": "See docs/invariants/P0-COMPLETION.md for HEAD",
        "static": {
            "connect_count": static["connect_count"],
            "exec_count": static["exec_count"],
            "dynamic_sql_count": static["dynamic_sql_count"],
            "writer_count": static["writer_count"],
            "reader_count": static["reader_count"],
            "tables": sorted(static_tables),
            "top_files": list(static["by_file"].items())[:20],
        },
        "runtime_focused_suite": runtime["summary"],
        "workflow_smoke": {
            "steps": smoke["steps"],
            "sql_events": smoke["sql_summary"].get("event_count"),
        },
        "table_reconcile": {
            "static_only": sorted(static_tables - rt_tables),
            "runtime_only": sorted(rt_tables - static_tables),
            "both": sorted(static_tables & rt_tables),
        },
        "identity_and_lifecycle_tables": identity,
        "static_identity_writer_files": static_write_files,
        "runtime_top_file_names": sorted(runtime_files)[:80],
    }
    path = ROOT / "artifacts/p0/reconcile.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(path),
        "static_tables": len(static_tables),
        "runtime_tables": len(rt_tables),
        "static_only": out["table_reconcile"]["static_only"],
        "runtime_events": runtime["summary"]["event_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
