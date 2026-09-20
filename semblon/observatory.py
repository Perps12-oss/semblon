"""Engineering Observatory — snapshot / compare / stage-enter.

Not a development gate. --promote is the only failing path.
Accuracy FAR/FRR is printed only for a frozen confirmatory set that is powered.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from semblon.export import STRONG_MIN_INTRA

STAGES = (
    "S0",
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
)

# What to check when *entering* a stage. S2 is parallel to 0.4; S3 still checks S1.
PREVIOUS = {
    "S0": None,
    "S1": "S0",
    "S2": "S1",
    "S3": "S1",
    "S4": "S3",
    "S5": "S4",
    "S6": "S5",
    "S7": "S4",
    "S8": "S6",
    "S9": "S8",
}

# Hypotheses — not frozen. Tune after a real dump.
REVIEW_UP_FRAC = 0.20
RSS_UP_FRAC = 0.25
TIME_UP_FRAC = 1.00  # 2×


class ObservatoryError(ValueError):
    pass


def golden_path(store: Path, stage: str) -> Path:
    stage = stage.upper()
    return Path(store).resolve().parent / "observatory" / f"golden-{stage}.json"


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise ObservatoryError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _json_obj(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return v if isinstance(v, dict) else {}


def snapshot(store: Path, run_id: str, strong_min_intra: float = STRONG_MIN_INTRA) -> dict:
    """Read-only board from a run. Does not write the store."""
    conn = _connect_ro(store)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise ObservatoryError(f"unknown run: {run_id}")

    def n(sql: str, args=()) -> int:
        return int(conn.execute(sql, args).fetchone()[0])

    faces = n("SELECT COUNT(*) FROM faces WHERE run_id=?", (run_id,))
    ok = n("SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok'", (run_id,))
    low = n("SELECT COUNT(*) FROM faces WHERE run_id=? AND status='low_quality'", (run_id,))
    rej = n("SELECT COUNT(*) FROM faces WHERE run_id=? AND status='rejected'", (run_id,))
    clustered = n(
        "SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok' AND cluster_id IS NOT NULL",
        (run_id,),
    )
    unassigned = n(
        "SELECT COUNT(*) FROM faces WHERE run_id=? AND status='ok' AND cluster_id IS NULL",
        (run_id,),
    )
    n_clusters = n("SELECT COUNT(*) FROM clusters WHERE run_id=?", (run_id,))
    review = n(
        """SELECT COUNT(*) FROM clusters WHERE run_id=?
           AND (min_intra IS NULL OR min_intra < ?)""",
        (run_id, strong_min_intra),
    )
    strong = n_clusters - review
    worst = conn.execute(
        "SELECT MIN(min_intra) FROM clusters WHERE run_id=? AND min_intra IS NOT NULL",
        (run_id,),
    ).fetchone()[0]
    from semblon.eval import accuracy_board

    accuracy = accuracy_board(conn)
    conn.close()

    per_1k = None
    if ok:
        per_1k = round(1000.0 * review / ok, 2)

    return {
        "kind": "semblon-observatory-snapshot",
        "taken_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "pack_id": run["pack_id"],
        "arch": run["arch"],
        "execution": run["execution"],
        "software_version": run["software_version"],
        "accuracy": accuracy,
        "detection": {
            "faces": faces,
            "ok": ok,
            "low_quality": low,
            "rejected": rej,
        },
        "clustering": {
            "clusters": n_clusters,
            "clustered": clustered,
            "unassigned": unassigned,
            "review_required": review,
            "strong": strong,
            "worst_min_intra": worst,
            "strong_min_intra": strong_min_intra,
        },
        "effort": {
            "review_clusters": review,
            "review_per_1k_ok": per_1k,
        },
        "speed": {
            "timings": _json_obj(run["timings_json"]),
            "peak_rss_mb": run["peak_rss_mb"],
        },
    }


def freeze(
    store: Path,
    run_id: str,
    stage: str,
    out: Path | None = None,
    notes: str | None = None,
) -> dict:
    """Write golden-{stage}.json beside the store. Optional human-review notes."""
    stage = stage.upper()
    if stage not in STAGES:
        raise ObservatoryError(f"unknown stage: {stage}")
    board = snapshot(store, run_id)
    board["stage"] = stage
    board["frozen"] = True
    if notes is not None:
        text = str(notes).strip()
        if text:
            board["notes"] = text
    path = Path(out) if out else golden_path(store, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    board["golden"] = str(path)
    return board


def _rel(old, new) -> float | None:
    if old in (None, 0) or new is None:
        return None
    try:
        return (float(new) - float(old)) / abs(float(old))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def compare_boards(golden: dict, current: dict) -> dict:
    notes: list[str] = []
    marks: dict[str, str] = {}

    if golden.get("pack_id") != current.get("pack_id"):
        return {
            "verdict": "not_measurable",
            "marks": {"pack_id": "not_measurable"},
            "notes": ["pack_id mismatch — boards are not comparable"],
            "golden_run": golden.get("run_id"),
            "current_run": current.get("run_id"),
        }

    g_acc = (golden.get("accuracy") or {}).get("status")
    c_acc = (current.get("accuracy") or {}).get("status")
    if g_acc in ("not_measurable", "underpowered") or c_acc in (
        "not_measurable",
        "underpowered",
    ):
        marks["accuracy"] = "not_measurable"
        notes.append("accuracy not measurable (no powered confirmatory eval)")
    else:
        marks["accuracy"] = "ok"

    g_rev = (golden.get("clustering") or {}).get("review_required")
    c_rev = (current.get("clustering") or {}).get("review_required")
    frac = _rel(g_rev, c_rev)
    if g_rev is None or c_rev is None:
        marks["effort"] = "not_measurable"
    elif frac is not None and frac > REVIEW_UP_FRAC:
        marks["effort"] = "regression"
        notes.append(f"review_required {g_rev} → {c_rev} (>{REVIEW_UP_FRAC:.0%} up)")
    elif frac is not None and frac < -0.05:
        marks["effort"] = "improvement"
    else:
        marks["effort"] = "ok"

    g_rss = (golden.get("speed") or {}).get("peak_rss_mb")
    c_rss = (current.get("speed") or {}).get("peak_rss_mb")
    frac = _rel(g_rss, c_rss)
    if g_rss is None or c_rss is None:
        marks["rss"] = "not_measurable"
    elif frac is not None and frac > RSS_UP_FRAC:
        marks["rss"] = "regression"
        notes.append(f"peak_rss_mb {g_rss} → {c_rss}")
    else:
        marks["rss"] = "ok"

    # Prefer named ingest/cluster seconds if present.
    g_t = (golden.get("speed") or {}).get("timings") or {}
    c_t = (current.get("speed") or {}).get("timings") or {}
    time_keys = [k for k in ("total_s", "cluster_s", "ingest_s") if k in g_t and k in c_t]
    if not time_keys:
        marks["speed"] = "not_measurable"
    else:
        marks["speed"] = "ok"
        for k in time_keys:
            f = _rel(g_t.get(k), c_t.get(k))
            if f is not None and f > TIME_UP_FRAC:
                marks["speed"] = "regression"
                notes.append(f"{k} {g_t.get(k)} → {c_t.get(k)}")
                break

    if "regression" in marks.values():
        verdict = "regression"
    elif "improvement" in marks.values() and all(
        v in ("ok", "improvement", "not_measurable") for v in marks.values()
    ):
        verdict = "improvement"
    elif all(v == "not_measurable" for v in marks.values()):
        verdict = "not_measurable"
    else:
        verdict = "ok"

    return {
        "verdict": verdict,
        "marks": marks,
        "notes": notes,
        "golden_run": golden.get("run_id"),
        "current_run": current.get("run_id"),
        "golden_stage": golden.get("stage"),
    }


def load_golden(path: Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ObservatoryError(f"no golden: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def compare_run(store: Path, run_id: str, golden_file: Path) -> dict:
    golden = load_golden(golden_file)
    current = snapshot(store, run_id)
    rec = compare_boards(golden, current)
    rec["current"] = current
    rec["golden_path"] = str(Path(golden_file).resolve())
    return rec


def enter_stage(
    store: Path,
    run_id: str,
    stage: str,
    *,
    promote: bool = False,
) -> dict:
    """Auto-check completed-stage golden when starting `stage`. Never blocks unless promote."""
    stage = stage.upper()
    if stage not in STAGES:
        raise ObservatoryError(f"unknown stage: {stage}")
    prev = PREVIOUS.get(stage)
    rec: dict = {
        "entering": stage,
        "checks": prev,
        "promote": promote,
    }
    if prev is None:
        rec["verdict"] = "ok"
        rec["notes"] = ["S0 has no previous golden"]
        return rec
    path = golden_path(store, prev)
    if not path.is_file():
        rec["verdict"] = "not_measurable"
        rec["notes"] = [
            f"no golden for completed {prev} at {path}; freeze after the dump to enable auto-check"
        ]
        rec["golden_path"] = str(path)
        return rec
    rec.update(compare_run(store, run_id, path))
    rec["entering"] = stage
    rec["checks"] = prev
    rec["promote"] = promote
    return rec
