"""Refuse fake PASS — pass=True requires verified=True."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping


class FakePassError(ValueError):
    """Raised when a result claims PASS without verification."""


def assert_no_fake_pass(result: Mapping[str, Any]) -> None:
    """Raise if ``pass`` is true while ``verified`` is false.

    Product PASS without a real measurement is forbidden. Harness tests may
    emit ``verified=True, pass=False`` via simulate-fail; they must never emit
    ``pass=True, verified=False``.
    """
    if bool(result.get("pass")) and not bool(result.get("verified")):
        cid = result.get("criterion_id", "<unknown>")
        raise FakePassError(
            f"fake PASS refused for criterion {cid!r}: "
            "pass=True requires verified=True (real OS/toolkit measurement)"
        )


def mark_unverified(reason: str, *, criterion_id: str | None = None) -> dict[str, Any]:
    """Return an honest unverified result shell (never a PASS)."""
    out: dict[str, Any] = {
        "verified": False,
        "pass": False,
        "status": "unverified",
        "metrics": {},
        "notes": reason,
    }
    if criterion_id is not None:
        out["criterion_id"] = criterion_id
    return out


def finalize(result: MutableMapping[str, Any]) -> dict[str, Any]:
    """Normalize required keys and refuse fake PASS before returning."""
    for key in ("criterion_id", "verified", "pass", "metrics", "notes", "status"):
        if key not in result:
            raise KeyError(f"measurement result missing required key: {key!r}")
    assert_no_fake_pass(result)
    return dict(result)
