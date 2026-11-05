"""P0 Source 3 — scripted workflow smoke (no identity weights required).

Exercises: init store, add folder stills via library paths available without
FaceKit, category coverage reads, search empty path, erasure wipe, interrupted
run stamp. Does not download packs. Parameter values are never logged.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def main() -> int:
    os.environ.setdefault("SEMBLON_P0_SQL_TRACE", "1")
    from p0.sql_runtime_trace import dump, install, reset, summary

    install()
    reset()

    from semblon.application import Application
    from semblon.category_backfill import coverage_report, recover_interrupted
    from semblon.process import default_store_path  # noqa: F401 — path probe only
    from semblon.store import connect, init_db, stamp_unfinished_runs
    from semblon.erasure import wipe_library

    steps: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="semblon-p0-") as tmp:
        tmp_path = Path(tmp)
        store = tmp_path / "store.sqlite"
        folder = tmp_path / "photos"
        folder.mkdir()
        # Tiny valid PNG (1x1).
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        (folder / "a.png").write_bytes(png)

        conn = connect(store)
        init_db(conn)
        steps.append({"step": "init_db", "schema": conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]})
        # Seed a synthetic unfinished run for interruption recovery.
        conn.execute(
            """INSERT INTO runs(run_id, started_at, software_version, pack_id,
               embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                "p0-unfinished",
                "2026-01-01T00:00:00+00:00",
                "p0",
                "p0-pack",
                1,
                "l2",
                "{}",
                "{}",
                "x64",
                "native",
            ),
        )
        conn.commit()
        stamped = stamp_unfinished_runs(conn)
        steps.append({"step": "stamp_unfinished_runs", "stamped": stamped})
        # category_coverage interrupt recovery path
        conn.execute(
            """INSERT INTO media(media_id, source_type, path, sha256)
               VALUES ('m1','folder',?, 'abc')""",
            (str(folder / "a.png"),),
        )
        conn.execute(
            """INSERT INTO category_coverage(
                 media_id, category, sha256, provider_id, provider_version, state,
                 attempt_count, frame_done, detail_done, updated_at)
               VALUES ('m1','people','abc','yunet_sface','v','running',1,0,0,'2026-01-01T00:00:00+00:00')"""
        )
        n = recover_interrupted(conn, "people")
        conn.commit()
        steps.append({"step": "recover_interrupted", "rows": n})
        conn.close()

        report = coverage_report(store, "people")
        steps.append({"step": "coverage_report", "completed": report.get("completed"), "state_keys": sorted(report.keys())})

        app = Application(store)
        steps.append({"step": "application", "busy": bool(app.busy), "state": str(app.state)})
        try:
            from semblon.search import search_people, search_text

            people = search_people(store)
            text = search_text(store, "nothing-should-match-p0")
            steps.append(
                {
                    "step": "search",
                    "people_keys": sorted(people.keys()) if isinstance(people, dict) else type(people).__name__,
                    "text_keys": sorted(text.keys()) if isinstance(text, dict) else type(text).__name__,
                }
            )
        except Exception as exc:  # noqa: BLE001 — inventory must record failure modes
            steps.append({"step": "search", "error": type(exc).__name__, "detail": str(exc)[:120]})

        wipe = wipe_library(store)
        steps.append(
            {
                "step": "wipe_library",
                "tables": wipe.get("tables") if isinstance(wipe, dict) else wipe,
                "erased": wipe.get("erased") if isinstance(wipe, dict) else None,
            }
        )
        app.shutdown(timeout=5.0)

    out = ROOT / "artifacts" / "p0" / "workflow_smoke.json"
    stats = dump(ROOT / "artifacts" / "p0" / "workflow_smoke_sql_trace.json")
    payload = {
        "steps": steps,
        "sql_summary": stats,
        "trace_summary": summary().__dict__,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "events": stats.get("event_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
