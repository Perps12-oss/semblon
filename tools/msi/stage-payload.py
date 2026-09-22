#!/usr/bin/env python3
"""Stage a Semblon code payload for MSI packaging.

Never copies buffalo_l, InsightFace model caches, .venv, or ONNX weights.
Runs on Linux or Windows so the agent can validate the stage path portably.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# Hard refuse if any staged path matches these (case-insensitive).
FORBIDDEN_NAME_RE = re.compile(
    r"(buffalo_l|\.insightface|\.onnx$|antelopev2|w600k_r50)",
    re.IGNORECASE,
)

# Top-level paths never staged.
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv-arm64-perf",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "semblon.egg-info",
    "node_modules",
    "payload",
    "dist",
    "build",
    ".insightface",
}

SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".onnx", ".pth", ".pt", ".bin"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return True
    if FORBIDDEN_NAME_RE.search(str(rel).replace("\\", "/")):
        return True
    return False


def _assert_not_forbidden(path: Path, root: Path) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    if FORBIDDEN_NAME_RE.search(rel):
        raise SystemExit(
            f"REFUSED: forbidden weight/cache path in payload: {rel}\n"
            "buffalo_l redistribution is UNAVAILABLE — see docs/licenses.md"
        )


# Allowlisted relative paths / globs from repo root.
ALLOWLIST = [
    "semblon.cmd",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "AGENTS.md",
    "docs/PACKAGING.md",
    "docs/licenses.md",
    "tools/install-windows.ps1",
    "tools/uninstall-windows.ps1",
    "tools/semblon-interactive.ps1",
    "tools/msi/bootstrap-install.ps1",
]


def _copy_tree(src: Path, dst: Path, repo: Path) -> list[Path]:
    copied: list[Path] = []
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path, repo):
            continue
        _assert_not_forbidden(path, repo)
        rel = path.relative_to(repo)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def stage(repo: Path, out: Path, clean: bool = True) -> list[Path]:
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []

    # Full Python package (identity code; no weights in-tree).
    pkg = repo / "semblon"
    if not pkg.is_dir():
        raise SystemExit(f"missing package dir: {pkg}")
    copied.extend(_copy_tree(pkg, out, repo))

    for rel in ALLOWLIST:
        src = repo / rel
        if not src.is_file():
            # Optional docs may be absent in sparse checkouts; require core files.
            if rel.startswith("docs/") or rel.startswith("packaging/"):
                continue
            if rel.startswith("tools/msi/") and rel.endswith(".py"):
                continue
            raise SystemExit(f"missing required stage file: {rel}")
        if not src.is_file():
            continue
        _assert_not_forbidden(src, repo)
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)

    # Marker so launchers know this is an MSI/code install layout (not a git checkout).
    marker = out / ".semblon-msi-install"
    marker.write_text(
        "Semblon MSI code install (no buffalo_l weights).\n"
        "Store: %LOCALAPPDATA%\\Semblon\n"
        "See docs/licenses.md\n",
        encoding="utf-8",
    )
    copied.append(marker)

    # Final scan of staged tree.
    for path in out.rglob("*"):
        if path.is_file():
            _assert_not_forbidden(path, out)

    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root (default: two levels above this script)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output payload directory (default: packaging/msi/payload)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Do not delete existing --out before staging",
    )
    args = parser.parse_args(argv)
    repo = (args.repo or _repo_root()).resolve()
    out = (args.out or (repo / "packaging" / "msi" / "payload")).resolve()
    copied = stage(repo, out, clean=not args.keep)
    print(f"staged {len(copied)} files -> {out}")
    print("weights: NOT included (buffalo_l redistribution UNAVAILABLE)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
