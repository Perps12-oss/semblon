"""Record FaceKit owner-pack evidence. Does not download weights.

Exit 0 only when assert_face_pack_ready succeeds. Writes a JSON evidence file
for the Gate B / issue 06 record (commit, Python, pin digests).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("facekit-owner-evidence.json"),
        help="JSON evidence path",
    )
    parser.add_argument(
        "--pack-dir",
        type=Path,
        default=None,
        help="Optional pack directory (else SEMBLON_FACE_PACK / FACEKIT_PACK_DIR / engine default)",
    )
    args = parser.parse_args(argv)

    pack_override = args.pack_dir
    if pack_override is None:
        for key in ("SEMBLON_FACE_PACK", "FACEKIT_PACK_DIR"):
            raw = (os.environ.get(key) or "").strip()
            if raw:
                pack_override = Path(raw)
                break

    from semblon.engine import ModelPackError, assert_face_pack_ready, face_pack_dir

    evidence = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pack_dir": str(pack_override or face_pack_dir()),
        "status": "FAILED",
        "pin": None,
        "error": None,
    }
    try:
        if pack_override is not None:
            pin = assert_face_pack_ready(pack_override)
        else:
            pin = assert_face_pack_ready()
        evidence["status"] = "PASS"
        evidence["pin"] = pin
    except ModelPackError as exc:
        evidence["error"] = str(exc)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"owner pack missing or unpinned: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — evidence must still land
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(evidence["error"], file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "files": len(pin or {})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
