"""Aggressive near-duplicate (A) validation — OpenCV aHash/dHash + Hamming."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from semblon.duplicates import (
    NEAR_HAMMING_THRESHOLD,
    NEAR_KIND,
    ahash64,
    dhash64,
    find_near_duplicate_groups,
    hamming64,
    perceptual_distance,
    similarity_basis_label,
)
from semblon.engine import _sha256_file
from semblon.store import connect, init_db

cv2 = pytest.importorskip("cv2")


def _seed_media(store: Path, items: list[tuple[str, Path]]) -> None:
    con = connect(store)
    try:
        init_db(con)
        for mid, path in items:
            digest = _sha256_file(path)
            con.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (
                    mid,
                    "folder",
                    str(path),
                    digest,
                    64,
                    64,
                    0,
                    path.stat().st_size,
                ),
            )
        con.commit()
    finally:
        con.close()


def _base_scene(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((128, 128, 3), dtype=np.uint8)
    img[:, :] = (40, 90, 160)
    # Distinct structure — gradients + rectangles (stable under mild transforms).
    for y in range(128):
        img[y, :, 0] = np.clip(40 + y, 0, 255)
    cv2.rectangle(img, (20, 20), (70, 80), (220, 180, 40), -1)
    cv2.circle(img, (90, 40), 18, (30, 200, 90), -1)
    noise = rng.integers(0, 12, size=img.shape, dtype=np.uint8)
    return cv2.add(img, noise)


def _write_jpg(path: Path, bgr: np.ndarray, quality: int = 90) -> None:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    assert ok
    path.write_bytes(buf.tobytes())


def _write_png(path: Path, bgr: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", bgr)
    assert ok
    path.write_bytes(buf.tobytes())


def test_similarity_basis_labels_distinct():
    assert "Exact" in similarity_basis_label("exact")
    assert "Near" in similarity_basis_label("near")
    assert "Whole" in similarity_basis_label("whole")
    assert "colour histogram" in similarity_basis_label("whole").lower()
    assert "region" in similarity_basis_label("region").lower()
    assert "colour histogram" in similarity_basis_label("region").lower()


def test_aggressive_near_duplicate_fixture_matrix(tmp_path):
    """Cases 1–5 should group; 6–7 must not (threshold-tuned)."""
    folder = tmp_path / "photos"
    folder.mkdir()
    base = _base_scene()

    # 1 same / recompressed JPEG
    p_orig = folder / "orig.jpg"
    p_rejpg = folder / "rejpg.jpg"
    _write_jpg(p_orig, base, quality=95)
    _write_jpg(p_rejpg, base, quality=60)

    # 2 resized
    p_resize = folder / "resize.jpg"
    resized = cv2.resize(base, (96, 96), interpolation=cv2.INTER_AREA)
    _write_jpg(p_resize, resized, quality=90)

    # 3 resized + recompressed
    p_resize_re = folder / "resize_re.jpg"
    _write_jpg(p_resize_re, resized, quality=55)

    # 4 slight crop
    p_crop = folder / "crop.jpg"
    crop = base[8:120, 8:120]
    crop = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA)
    _write_jpg(p_crop, crop, quality=90)

    # 5 brightness / contrast
    p_bright = folder / "bright.jpg"
    bright = cv2.convertScaleAbs(base, alpha=1.25, beta=18)
    _write_jpg(p_bright, bright, quality=90)

    # 6 visually similar but different image (same palette, different shapes)
    p_similar = folder / "similar_diff.jpg"
    other = _base_scene(seed=99)
    other = cv2.flip(other, 1)
    cv2.rectangle(other, (10, 90), (50, 120), (10, 10, 240), -1)
    _write_jpg(p_similar, other, quality=90)

    # 7 unrelated
    p_unrel = folder / "unrelated.jpg"
    unrel = np.zeros((128, 128, 3), dtype=np.uint8)
    unrel[:, :] = (200, 30, 30)
    for i in range(0, 128, 8):
        unrel[i : i + 3, :] = (10, 10, 10)
    _write_jpg(p_unrel, unrel, quality=90)

    # Pairwise distance sanity before grouping.
    g0 = cv2.imdecode(np.frombuffer(p_orig.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    pairs_should_near = [p_rejpg, p_resize, p_resize_re, p_crop, p_bright]
    for p in pairs_should_near:
        g = cv2.imdecode(np.frombuffer(p.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        dist = perceptual_distance(g0, g)
        assert dist <= NEAR_HAMMING_THRESHOLD, f"{p.name} dist={dist}"

    for p in (p_similar, p_unrel):
        g = cv2.imdecode(np.frombuffer(p.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        dist = perceptual_distance(g0, g)
        assert dist > NEAR_HAMMING_THRESHOLD, f"{p.name} dist={dist} should not near-match"

    store = tmp_path / "s.sqlite"
    paths = [
        ("m_orig", p_orig),
        ("m_rejpg", p_rejpg),
        ("m_resize", p_resize),
        ("m_resize_re", p_resize_re),
        ("m_crop", p_crop),
        ("m_bright", p_bright),
        ("m_similar", p_similar),
        ("m_unrel", p_unrel),
    ]
    _seed_media(store, paths)

    result = find_near_duplicate_groups(store, threshold=NEAR_HAMMING_THRESHOLD)
    assert result["status"] == "SUCCESS"
    assert result["kind"] == NEAR_KIND
    assert result["group_count"] >= 1

    # Collect media ids that share a group with m_orig.
    near_of_orig: set[str] = set()
    for g in result["groups"]:
        mids = {str(m) for m in (g.get("media_ids") or []) if m}
        if "m_orig" in mids:
            near_of_orig |= mids
    assert "m_orig" in near_of_orig
    for mid in ("m_rejpg", "m_resize", "m_resize_re", "m_crop", "m_bright"):
        assert mid in near_of_orig, f"{mid} should near-group with orig"
    assert "m_similar" not in near_of_orig
    assert "m_unrel" not in near_of_orig


def test_ahash_dhash_deterministic():
    img = _base_scene()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    assert ahash64(gray) == ahash64(gray)
    assert dhash64(gray) == dhash64(gray)
    assert hamming64(ahash64(gray), ahash64(gray)) == 0
