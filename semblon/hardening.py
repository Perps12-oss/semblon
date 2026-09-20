"""Hardware/runtime and product lifecycle hardening snapshots."""

from __future__ import annotations

import platform
from pathlib import Path

from semblon.engine import onnx_providers, process_arch, process_execution, select_execution_provider
from semblon.opencv_probe import probe_opencv
from semblon.process import default_store_path


def hardware_matrix() -> dict:
    sel = select_execution_provider(prefer_gpu=True)
    return {
        "os": platform.system().lower(),
        "os_version": platform.version(),
        "process_arch": process_arch(),
        "execution": process_execution(),
        "ort_providers": onnx_providers(),
        "selected_provider": sel.get("chosen"),
        "gpu_listed": bool(sel.get("gpu")),
        "opencv_probe": probe_opencv(timeout_s=8.0),
        "note": "GPU listed means EP visibility, not full workload validation.",
    }


def product_lifecycle_status(repo_root: Path | None = None) -> dict:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    install = root / "tools" / "install-windows.ps1"
    uninstall = root / "tools" / "uninstall-windows.ps1"
    launcher = root / "tools" / "semblon-interactive.ps1"
    return {
        "repo_root": str(root),
        "scripts": {
            "install_windows": {"path": str(install), "present": install.is_file()},
            "uninstall_windows": {"path": str(uninstall), "present": uninstall.is_file()},
            "interactive_launcher": {"path": str(launcher), "present": launcher.is_file()},
        },
        "default_store": str(default_store_path()),
        "first_run": {
            "home_command": "python -m semblon home",
            "store_created_on_ingest": True,
        },
    }


def hardening_snapshot(repo_root: Path | None = None) -> dict:
    return {
        "hardware_matrix": hardware_matrix(),
        "product_lifecycle": product_lifecycle_status(repo_root),
    }
