"""Read-only markdown report. Writes --out only. Never the store."""

from __future__ import annotations

from pathlib import Path

from semblon.stats import StatsError, stats


class ReportError(ValueError):
    pass


def render_report(rec: dict) -> str:
    det = rec.get("detection") or {}
    clu = rec.get("clustering") or {}
    acc = rec.get("accuracy") or {}
    kinds = rec.get("decisions_by_kind") or {}
    kind_line = ", ".join(f"{k}={v}" for k, v in kinds.items()) or "none"
    acc_line = acc.get("status") or "unknown"
    if acc.get("status") == "measurable":
        acc_line = f"measurable FAR={acc.get('far')} FRR={acc.get('frr')}"
    elif acc.get("reason"):
        acc_line = f"{acc.get('status')} ({acc.get('reason')})"
    return (
        f"# Semblon report\n\n"
        f"- run: `{rec.get('run_id')}`\n"
        f"- pack: `{rec.get('pack_id')}`\n"
        f"- arch: {rec.get('arch')} {rec.get('execution')}\n\n"
        f"## Detection\n\n"
        f"- faces {det.get('faces')} · ok {det.get('ok')} · "
        f"low_quality {det.get('low_quality')} · rejected {det.get('rejected')}\n\n"
        f"## Clustering\n\n"
        f"- clusters {clu.get('clusters')} · clustered {clu.get('clustered')} · "
        f"unassigned {clu.get('unassigned')} · review {clu.get('review_required')} · "
        f"strong {clu.get('strong')}\n\n"
        f"## Persons\n\n"
        f"- active persons {rec.get('persons_active')} · named faces {rec.get('faces_named')}\n"
        f"- decisions {rec.get('decisions')} ({kind_line})\n\n"
        f"## Accuracy\n\n"
        f"- {acc_line}\n"
        f"- cluster is not a person. Unknown is valid.\n"
    )


def write_report(store: Path, run_id: str, out: Path) -> dict:
    try:
        rec = stats(store, run_id)
    except StatsError as e:
        raise ReportError(str(e)) from e
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render_report(rec)
    out.write_text(text, encoding="utf-8")
    return {
        "run_id": run_id,
        "out": str(out.resolve()),
        "bytes": out.stat().st_size,
        "note": "report did not write the store",
    }
