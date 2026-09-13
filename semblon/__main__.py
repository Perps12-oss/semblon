"""Allow `python -m semblon` from an editable install."""

from __future__ import annotations

from semblon.cli import main

raise SystemExit(main())
