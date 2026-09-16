"""Allow `python -m semblon` using the same CLI entry as the console script."""

from __future__ import annotations

from semblon.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
