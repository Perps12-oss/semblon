"""One runner per docs/R3-BRIEF.md §6 criterion.

Default path (no real OS/toolkit measurement): unverified / fail.
Optional ``simulate_fail`` may set verified=True with pass=False for harness
tests only. There is intentionally no simulate-pass path.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .refuse import finalize, mark_unverified

# Stable ids aligned with R3-BRIEF §6 order (1..6).
CRITERIA: tuple[tuple[str, str], ...] = (
    (
        "accent_suppress",
        "Fully suppress OS accent in every native control "
        "(focus, selection, toggle, progress).",
    ),
    (
        "mica_opaque",
        "Opaque achromatic surface over Mica without bleed.",
    ),
    (
        "frame_time_4k60",
        "< 16 ms frame time on 4K/60 video scrub.",
    ),
    (
        "wcag_aa",
        "WCAG AA on all custom controls, both themes.",
    ),
    (
        "virtualized_grid_10k",
        "10k-thumbnail virtualized grid without jank.",
    ),
    (
        "a11y_tree",
        "Native accessibility tree on custom-drawn surfaces "
        "(face boxes, compare cells).",
    ),
)

CRITERION_IDS: tuple[str, ...] = tuple(cid for cid, _ in CRITERIA)

_UNVERIFIED_NOTE = (
    "no real OS/toolkit measurement provided; "
    "status remains unverified (refuse silent PASS)"
)


def _synthetic_fail(criterion_id: str, *, notes: str | None = None) -> dict[str, Any]:
    """Harness-only: verified fail. Never a product PASS."""
    return finalize(
        {
            "criterion_id": criterion_id,
            "verified": True,
            "pass": False,
            "status": "fail",
            "metrics": {"synthetic": True, "simulate_fail": True},
            "notes": notes
            or "synthetic fail for harness testing (not a product measurement)",
        }
    )


def _unverified(criterion_id: str) -> dict[str, Any]:
    return finalize(mark_unverified(_UNVERIFIED_NOTE, criterion_id=criterion_id))


def _eval_bool_gate(
    criterion_id: str,
    measurement: Mapping[str, Any],
    *,
    required_true: tuple[str, ...],
    metrics_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Evaluate an externally supplied measurement dict (host-collected).

    Callers must supply honest host evidence. Missing required keys → fail
    (verified), not PASS. No path invents success from empty input.
    """
    metrics: dict[str, Any] = {
        k: measurement.get(k) for k in (*required_true, *metrics_keys) if k in measurement
    }
    missing = [k for k in required_true if k not in measurement]
    if missing:
        return finalize(
            {
                "criterion_id": criterion_id,
                "verified": True,
                "pass": False,
                "status": "fail",
                "metrics": metrics,
                "notes": f"measurement incomplete; missing keys: {missing}",
            }
        )
    ok = all(bool(measurement[k]) for k in required_true)
    return finalize(
        {
            "criterion_id": criterion_id,
            "verified": True,
            "pass": ok,
            "status": "pass" if ok else "fail",
            "metrics": metrics,
            "notes": "evaluated from supplied host measurement",
        }
    )


def _run(
    criterion_id: str,
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
    evaluate: Callable[[str, Mapping[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if simulate_fail:
        return _synthetic_fail(criterion_id)
    if measurement is None:
        return _unverified(criterion_id)
    if evaluate is None:
        raise TypeError(f"{criterion_id}: evaluate required when measurement is set")
    return evaluate(criterion_id, measurement)


def run_accent_suppress(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.1 — OS accent suppressed on native controls."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        return _eval_bool_gate(
            cid,
            m,
            required_true=(
                "focus_accent_suppressed",
                "selection_accent_suppressed",
                "toggle_accent_suppressed",
                "progress_accent_suppressed",
            ),
        )

    return _run(
        "accent_suppress",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


def run_mica_opaque(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.2 — Opaque achromatic surface over Mica without bleed."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        return _eval_bool_gate(
            cid,
            m,
            required_true=("opaque_achromatic", "no_mica_bleed"),
            metrics_keys=("backdrop",),
        )

    return _run(
        "mica_opaque",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


def run_frame_time_4k60(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.3 — < 16 ms frame time on 4K/60 video scrub."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        if "frame_time_ms" not in m:
            return finalize(
                {
                    "criterion_id": cid,
                    "verified": True,
                    "pass": False,
                    "status": "fail",
                    "metrics": {},
                    "notes": "measurement incomplete; missing keys: ['frame_time_ms']",
                }
            )
        ft = float(m["frame_time_ms"])
        ok = ft < 16.0
        return finalize(
            {
                "criterion_id": cid,
                "verified": True,
                "pass": ok,
                "status": "pass" if ok else "fail",
                "metrics": {
                    "frame_time_ms": ft,
                    "threshold_ms": 16.0,
                    "resolution": m.get("resolution", "4K"),
                    "scrub_hz": m.get("scrub_hz", 60),
                },
                "notes": "evaluated from supplied host measurement",
            }
        )

    return _run(
        "frame_time_4k60",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


def run_wcag_aa(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.4 — WCAG AA on all custom controls, both themes."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        return _eval_bool_gate(
            cid,
            m,
            required_true=("light_theme_aa", "dark_theme_aa", "all_custom_controls"),
            metrics_keys=("min_contrast_ratio",),
        )

    return _run(
        "wcag_aa",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


def run_virtualized_grid_10k(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.5 — 10k-thumbnail virtualized grid without jank."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        if "thumbnail_count" not in m or "jank_observed" not in m:
            missing = [
                k for k in ("thumbnail_count", "jank_observed") if k not in m
            ]
            return finalize(
                {
                    "criterion_id": cid,
                    "verified": True,
                    "pass": False,
                    "status": "fail",
                    "metrics": {k: m.get(k) for k in ("thumbnail_count", "jank_observed") if k in m},
                    "notes": f"measurement incomplete; missing keys: {missing}",
                }
            )
        count = int(m["thumbnail_count"])
        jank = bool(m["jank_observed"])
        ok = count >= 10_000 and not jank
        return finalize(
            {
                "criterion_id": cid,
                "verified": True,
                "pass": ok,
                "status": "pass" if ok else "fail",
                "metrics": {
                    "thumbnail_count": count,
                    "jank_observed": jank,
                    "scroll_fps": m.get("scroll_fps"),
                },
                "notes": "evaluated from supplied host measurement",
            }
        )

    return _run(
        "virtualized_grid_10k",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


def run_a11y_tree(
    *,
    simulate_fail: bool = False,
    measurement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """§6.6 — Native accessibility tree on custom-drawn surfaces."""

    def _eval(cid: str, m: Mapping[str, Any]) -> dict[str, Any]:
        return _eval_bool_gate(
            cid,
            m,
            required_true=(
                "face_boxes_in_tree",
                "compare_cells_in_tree",
                "native_provider",
            ),
            metrics_keys=("provider_name",),
        )

    return _run(
        "a11y_tree",
        simulate_fail=simulate_fail,
        measurement=measurement,
        evaluate=_eval,
    )


_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "accent_suppress": run_accent_suppress,
    "mica_opaque": run_mica_opaque,
    "frame_time_4k60": run_frame_time_4k60,
    "wcag_aa": run_wcag_aa,
    "virtualized_grid_10k": run_virtualized_grid_10k,
    "a11y_tree": run_a11y_tree,
}


def run_all(
    *,
    simulate_fail: bool = False,
    measurements: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run all six §6 runners. Default: six unverified results."""
    measurements = measurements or {}
    out: list[dict[str, Any]] = []
    for cid in CRITERION_IDS:
        out.append(
            _RUNNERS[cid](
                simulate_fail=simulate_fail,
                measurement=measurements.get(cid),
            )
        )
    return out
