"""R3 bake-off harness — aggregate §6 criteria; never invent PASS.

Gate key: ``r3_bakeoff`` (SEMBLON_GATE_R3_BAKEOFF). Default OFF.
``main()`` may still run as a lab tool when the gate is OFF; the report
records ``gate_enabled=false``. Prefer ``is_enabled`` over ``require_enabled``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from semblon.gates import is_enabled  # noqa: E402

from tools.r3_bakeoff.criteria import (  # noqa: E402
    REJECTED_TOOLKITS,
    criterion_ids,
    default_results,
)

GATE_KEY = "r3_bakeoff"
EXPECTED_IDS = frozenset(criterion_ids())


def _normalize_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce a criterion result dict; unknowns stay non-passing."""
    cid = str(raw.get("id", ""))
    verified = bool(raw.get("verified", False))
    passed = bool(raw.get("pass", False))
    status = raw.get("status")
    if status is None:
        if verified and passed:
            status = "pass"
        elif verified and not passed:
            status = "fail"
        else:
            status = "unverified"
    status = str(status)
    # Never treat unverified / not_executed as a pass even if flags look wrong.
    if status in {"unverified", "not_executed"}:
        verified = False
        passed = False
    return {
        "id": cid,
        "label": raw.get("label", ""),
        "status": status,
        "verified": verified,
        "pass": passed and verified,
        "detail": raw.get("detail", ""),
    }


def _overall(results: Sequence[Mapping[str, Any]]) -> str:
    """PASS only when every expected criterion is verified and pass=True."""
    by_id = {r["id"]: r for r in results if r.get("id")}
    if set(by_id) != EXPECTED_IDS:
        return "incomplete"
    if not all(by_id[i]["verified"] and by_id[i]["pass"] for i in EXPECTED_IDS):
        if any(by_id[i]["verified"] and not by_id[i]["pass"] for i in EXPECTED_IDS if i in by_id):
            # At least one measured failure among a complete set → FAIL;
            # incomplete coverage of verified measurements stays incomplete
            # when any slot is still unverified.
            if all(by_id[i]["verified"] for i in EXPECTED_IDS):
                return "FAIL"
            return "incomplete"
        return "incomplete"
    return "PASS"


def run_bakeoff(criteria_results: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Aggregate criterion results into a bake-off report.

    Parameters
    ----------
    criteria_results:
        Iterable of per-criterion dicts (id, verified, pass, status, …).
        When None, runs stub measure_fns (all unverified).

    Returns
    -------
    Report dict. ``overall`` is ``PASS`` only if every §6 criterion has
    ``verified=True`` and ``pass=True``. Unrun stubs never yield PASS.
    """
    gate_on = is_enabled(GATE_KEY)
    raw_list = list(criteria_results) if criteria_results is not None else default_results()
    results = [_normalize_result(r) for r in raw_list]
    present = {r["id"] for r in results}
    missing = sorted(EXPECTED_IDS - present)
    # Drop unknown ids from overall consideration but keep them listed.
    overall = _overall(results)
    return {
        "harness": "r3_bakeoff",
        "source": "docs/R3-BRIEF.md §6",
        "gate_key": GATE_KEY,
        "gate_enabled": gate_on,
        "rejected_toolkits": list(REJECTED_TOOLKITS),
        "expected_criteria": list(criterion_ids()),
        "criteria": results,
        "missing_criteria": missing,
        "overall": overall,
        "policy": "never invent PASS; unverified/not_executed cannot pass",
    }


def main(argv: list[str] | None = None) -> int:
    """Lab CLI. Runs with gate OFF; report records gate_enabled."""
    parser = argparse.ArgumentParser(
        description="R3 toolkit bake-off harness (scaffold; gate default OFF)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full report as JSON",
    )
    args = parser.parse_args(argv)

    # Prefer is_enabled (record) over require_enabled (raise) so lab use works OFF.
    report = run_bakeoff()

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"r3_bakeoff overall={report['overall']} gate_enabled={report['gate_enabled']}")
        for c in report["criteria"]:
            print(
                f"  {c['id']}: status={c['status']} "
                f"verified={c['verified']} pass={c['pass']}"
            )
        if report["missing_criteria"]:
            print(f"  missing: {', '.join(report['missing_criteria'])}")
        print(f"  rejected_toolkits: {', '.join(report['rejected_toolkits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
