"""Results JSON writer for R3 §6 bake-off. Never invents PASS."""

from __future__ import annotations

import json
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
BRIEF_REF = "docs/R3-BRIEF.md §6"
CHECKLIST_REF = "docs/r3-artifacts/05-bake-off-checklist.md"

CRITERIA_META: list[dict[str, Any]] = [
    {
        "id": 1,
        "key": "os_accent_suppress",
        "title": "Fully suppress OS accent in every native control (focus, selection, toggle, progress).",
    },
    {
        "id": 2,
        "key": "opaque_achromatic_over_mica",
        "title": "Opaque achromatic surface over Mica without bleed.",
    },
    {
        "id": 3,
        "key": "scrub_frametime_4k60",
        "title": "< 16 ms frame time on 4K/60 video scrub.",
        "threshold": {"max_frame_ms": 16.0, "resolution": "3840x2160", "fps": 60},
    },
    {
        "id": 4,
        "key": "wcag_aa_custom_controls",
        "title": "WCAG AA on all custom controls, both themes.",
        "threshold": {"contrast_normal_text": 4.5, "contrast_large_text": 3.0, "contrast_ui": 3.0},
    },
    {
        "id": 5,
        "key": "virtualized_grid_10k",
        "title": "10k-thumbnail virtualized grid without jank.",
        "threshold": {"item_count": 10000, "target_scroll_fps": 60},
    },
    {
        "id": 6,
        "key": "a11y_tree_custom_drawn",
        "title": "Native accessibility tree on custom-drawn surfaces (face boxes, compare cells).",
    },
]

OVERALL_REASON = (
    "Overall PASS only if all six criteria.pass are true after human verification. "
    "Harness leaves overall.pass null. Do not soft-pass. Do not choose WinUI vs Qt here."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_machine() -> str:
    return socket.gethostname()


def default_os() -> str:
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def empty_criterion(meta: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": meta["id"],
        "key": meta["key"],
        "title": meta["title"],
        "status": "pending_human",
        "pass": None,
        "threshold": meta.get("threshold"),
        "measurements": {},
        "evidence_path": None,
        "notes": "",
        "human_steps": [],
        "probe": {
            "name": "",
            "attempted": False,
            "auto_capable": False,
            "detail": "",
        },
    }
    return row


def new_results_doc(
    *,
    toolkit: str = "",
    toolkit_version: str = "",
    operator: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "brief_ref": BRIEF_REF,
        "checklist_ref": CHECKLIST_REF,
        "run": {
            "toolkit": toolkit,
            "toolkit_version": toolkit_version,
            "machine": default_machine(),
            "os": default_os(),
            "operator": operator,
            "started_at": utc_now_iso(),
            "finished_at": None,
            "notes": notes,
        },
        "criteria": [empty_criterion(m) for m in CRITERIA_META],
        "overall": {
            "pass": None,
            "reason": OVERALL_REASON,
        },
    }


def write_results(path: Path, doc: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never let a probe flip overall.pass.
    doc["overall"]["pass"] = None
    doc["overall"]["reason"] = OVERALL_REASON
    for c in doc.get("criteria", []):
        # Harness may fill measurements/status; human owns pass.
        if "pass" not in c:
            c["pass"] = None
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def load_results(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def results_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "results"


def default_out_path(toolkit: str = "") -> Path:
    stamp = utc_now_iso().replace(":", "")
    safe = (toolkit or "unspecified").replace("/", "-").replace("\\", "-").replace(" ", "_")
    return results_dir() / f"bakeoff-{safe}-{stamp}.json"
