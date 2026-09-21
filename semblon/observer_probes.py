"""Capability probes for optional observers — import ≠ runnable.

Does not download models, claim GPU, or touch identity paths.
Contour objects remain a separate surface (not a detector pack).
"""

from __future__ import annotations

from typing import Any


def _probe(
    *,
    available: bool,
    runnable: bool,
    import_ok: bool,
    detail: str,
    verified: bool,
) -> dict[str, Any]:
    return {
        "available": bool(available),
        "runnable": bool(runnable),
        "import_ok": bool(import_ok),
        "detail": str(detail),
        "verified": bool(verified),
    }


def probe_ocr() -> dict[str, Any]:
    """OCR: pytesseract import vs tesseract binary capability."""
    try:
        import pytesseract
    except Exception as e:  # noqa: BLE001 — probe must not crash
        return _probe(
            available=False,
            runnable=False,
            import_ok=False,
            detail=f"unavailable: {type(e).__name__}",
            verified=True,
        )
    # Best-effort binary check; missing tesseract must not raise out of here.
    try:
        ver = pytesseract.get_tesseract_version()
        return _probe(
            available=True,
            runnable=True,
            import_ok=True,
            detail=f"pytesseract + tesseract {ver}",
            verified=True,
        )
    except Exception as e:  # noqa: BLE001
        return _probe(
            available=False,
            runnable=False,
            import_ok=True,
            detail=(
                f"pytesseract import ok; tesseract binary missing or unusable "
                f"({type(e).__name__})"
            ),
            verified=True,
        )


def probe_clip() -> dict[str, Any]:
    """CLIP: open_clip import vs API surface. Does not download weights."""
    try:
        import open_clip
    except Exception as e:  # noqa: BLE001
        return _probe(
            available=False,
            runnable=False,
            import_ok=False,
            detail=f"unavailable: {type(e).__name__}",
            verified=True,
        )
    if not hasattr(open_clip, "create_model_and_transforms"):
        return _probe(
            available=False,
            runnable=False,
            import_ok=True,
            detail="open_clip import ok but create_model_and_transforms missing",
            verified=True,
        )
    return _probe(
        available=True,
        runnable=True,
        import_ok=True,
        detail="open_clip import ok; weights not probed (no download)",
        verified=True,
    )


def probe_pose() -> dict[str, Any]:
    """Pose: mediapipe import vs solutions.pose API (import ≠ capability)."""
    try:
        import mediapipe as mp
    except Exception as e:  # noqa: BLE001
        return _probe(
            available=False,
            runnable=False,
            import_ok=False,
            detail=f"unavailable: {type(e).__name__}",
            verified=True,
        )
    ver = getattr(mp, "__version__", "?")
    has_pose = hasattr(mp, "solutions") and hasattr(getattr(mp, "solutions", None), "pose")
    if has_pose:
        return _probe(
            available=True,
            runnable=True,
            import_ok=True,
            detail=f"mediapipe {ver} solutions.pose",
            verified=True,
        )
    return _probe(
        available=False,
        runnable=False,
        import_ok=True,
        detail=(
            f"mediapipe {ver} installed but solutions.pose API not exposed "
            f"(not runnable for Semblon pose)"
        ),
        verified=True,
    )


def probe_all() -> dict[str, dict[str, Any]]:
    """Aggregate OCR / CLIP / pose honesty probes."""
    return {
        "ocr": probe_ocr(),
        "clip": probe_clip(),
        "pose": probe_pose(),
    }
