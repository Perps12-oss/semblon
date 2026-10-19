"""Local description model path. No download.

``SEMBLON_VLM_MODEL`` wins when it is set. Otherwise a confirmed install can
leave a ``pixel-describer`` marker under the Semblon model directory. That
marker runs the local colour description. It is not a fetched vision-language
weight, and it does not write face identity.
"""

from __future__ import annotations

import os
from pathlib import Path

MARKER_NAME = "pixel-describer.txt"
MARKER_TEXT = "pixel-describer\n"


class VlmInstallError(RuntimeError):
    """The local description marker could not be written."""


def vlm_model_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    return Path.home() / ".semblon" / "models" / "vlm"


def marker_path(root: Path | None = None) -> Path:
    return vlm_model_dir(root) / MARKER_NAME


def vlm_model_path(root: Path | None = None) -> str | None:
    """Env path when set, otherwise the installed local marker when that file exists."""
    env = (os.environ.get("SEMBLON_VLM_MODEL") or "").strip()
    if env:
        return env
    marker = marker_path(root)
    if marker.is_file():
        return str(marker)
    return None


def install_local_description(*, root: Path | None = None) -> dict:
    """Write the local pixel-describer marker. Does not contact the network."""
    dest = marker_path(root)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            already = dest.is_file() and dest.read_text(encoding="utf-8").startswith("pixel-describer")
        except UnicodeDecodeError:
            already = False
        if not already:
            dest.write_text(MARKER_TEXT, encoding="utf-8")
    except OSError as exc:
        raise VlmInstallError(f"description install failed: {exc.__class__.__name__}") from exc
    return {
        "state": "AVAILABLE",
        "path": str(dest),
        "kind": "pixel-describer",
        "changed": not already,
    }
