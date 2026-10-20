"""Labelled retrieval eval for the Lens-style ranking path.

Tuples are ``(highlight, relevant media_ids, hard negatives)``.
Synthetic reports ranks and whether each relevant hit sits above the
hard negatives. Precision is refused unless ``--eval-set confirmatory``.

Does not retune RRF, floors, or S1. Does not write identity. ANN stays
parked. The photographic patch eval remains the appearance regression.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from semblon.index_provider import index_seam_status
from semblon.query_spec import MODE_KIND, MODE_LOOK, parse_query_spec
from semblon.store import connect, init_db

EVAL_SET_SYNTHETIC = "synthetic"
EVAL_SET_CONFIRMATORY = "confirmatory"
EVAL_SETS = (EVAL_SET_SYNTHETIC, EVAL_SET_CONFIRMATORY)

FAMILY_BRAND_TEXT = "brand_text"
FAMILY_SAME_KIND = "same_kind"
FAMILY_SAME_LOOK = "same_look"
FAMILY_PART_VS_WHOLE = "part_vs_whole"
FAMILY_HARD_NEG_COLOUR = "hard_neg_colour"

_TEXT_BASIS = "Text in photos (OCR substring)"
_LOOK_BASIS = "Similar look"
_NANODET = "opencv-zoo-nanodet"


class LensEvalError(ValueError):
    pass


@dataclass(frozen=True)
class LensCase:
    """One labelled highlight. Not a person and not a confirmatory identity pair."""

    case_id: str
    family: str
    query_media_id: str
    relevant: tuple[str, ...]
    hard_negatives: tuple[str, ...]
    observations: tuple[dict, ...]
    query_spec: dict
    look_items: tuple[dict, ...]
    notes: str

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "family": self.family,
            "query_media_id": self.query_media_id,
            "relevant": list(self.relevant),
            "hard_negatives": list(self.hard_negatives),
            "query_spec": dict(self.query_spec),
            "notes": self.notes,
        }


def normalize_eval_set(value: str | None) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    if key in {EVAL_SET_CONFIRMATORY, "confirmatory_hard"}:
        return EVAL_SET_CONFIRMATORY
    if key in {EVAL_SET_SYNTHETIC, "", "default"}:
        return EVAL_SET_SYNTHETIC
    raise LensEvalError(f"unknown eval set: {value}")


def precision_allowed(eval_set: str | None) -> bool:
    return normalize_eval_set(eval_set) == EVAL_SET_CONFIRMATORY


def precision_refusal(eval_set: str | None) -> str:
    if not precision_allowed(eval_set):
        return "not confirmatory — precision refused"
    return "no frozen confirmatory Lens eval set"


def _look(media_id: str, score: float) -> dict:
    return {
        "media_id": media_id,
        "score": score,
        "match_norm": [0.0, 0.0, 1.0, 1.0],
    }


def labelled_cases() -> list[LensCase]:
    """Built-in synthetic tuples. Not a real-world photo benchmark."""
    return [
        LensCase(
            case_id="brand-acme",
            family=FAMILY_BRAND_TEXT,
            query_media_id="acme-query",
            relevant=("acme-hit",),
            hard_negatives=("acne-lookalike", "chair-red"),
            observations=(
                {"kind": "text", "payload": {"text": "ACME", "role": "ocr"}},
            ),
            query_spec={"mode": MODE_LOOK},
            look_items=(
                _look("acne-lookalike", 0.91),
                _look("chair-red", 0.88),
                _look("acme-hit", 0.31),
            ),
            notes="Readable brand. BM25 must lift ACME over a same-colour lookalike.",
        ),
        LensCase(
            case_id="kind-cup",
            family=FAMILY_SAME_KIND,
            query_media_id="cup-red",
            relevant=("cup-blue",),
            hard_negatives=("chair-red",),
            observations=(
                {"kind": "object", "payload": {"label": "cup", "class": "cup"}},
            ),
            query_spec={"mode": MODE_KIND},
            look_items=(
                _look("chair-red", 0.93),
                _look("cup-blue", 0.38),
            ),
            notes="Same kind, different instance. Object class must beat same-colour chair.",
        ),
        LensCase(
            case_id="look-red-cup",
            family=FAMILY_SAME_LOOK,
            query_media_id="cup-red",
            relevant=("cup-red-2",),
            hard_negatives=("cup-blue",),
            observations=(
                {"kind": "object", "payload": {"label": "cup", "class": "cup"}},
            ),
            query_spec={"mode": MODE_LOOK},
            look_items=(
                _look("cup-red-2", 0.94),
                _look("chair-red", 0.86),
                _look("cup-blue", 0.34),
            ),
            notes="Same look. Another red cup ranks above a blue cup of the same kind.",
        ),
        LensCase(
            case_id="part-logo",
            family=FAMILY_PART_VS_WHOLE,
            query_media_id="shirt-logo",
            relevant=("logo-hit", "acme-hit"),
            hard_negatives=("shirt-plain",),
            observations=(
                {"kind": "text", "payload": {"text": "ACME", "role": "ocr"}},
            ),
            query_spec={"mode": MODE_LOOK, "part_index": 0},
            look_items=(
                _look("shirt-plain", 0.90),
                _look("logo-hit", 0.22),
            ),
            notes="Search the mark, not the shirt. Logo text ranks above a plain shirt.",
        ),
        LensCase(
            case_id="colour-confuser",
            family=FAMILY_HARD_NEG_COLOUR,
            query_media_id="cup-red",
            relevant=("cup-red-2",),
            hard_negatives=("chair-red",),
            observations=(
                {"kind": "object", "payload": {"label": "cup", "class": "cup"}},
            ),
            query_spec={"mode": MODE_LOOK},
            look_items=(
                _look("chair-red", 0.96),
                _look("cup-red-2", 0.71),
            ),
            notes="Hard negative: same colour, different meaning. Fusion must not keep the chair first.",
        ),
    ]


def _swatch(bgr: tuple[int, int, int], size: int = 48) -> np.ndarray:
    return np.full((size, size, 3), bgr, dtype=np.uint8)


def _write_png(path: Path, image: np.ndarray) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise LensEvalError(f"could not write {path}")


def _insert_run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r-lens-eval", "t", "0.0.1", "lens-eval", 24, "l2", "{}", "{}", "x64", "emulated"),
    )


def _add_media(
    conn,
    root: Path,
    media_id: str,
    image: np.ndarray,
    *,
    text: str | None = None,
    objects: Iterable[str] = (),
    text_box: tuple[int, int, int, int] | None = None,
) -> None:
    from semblon.observers import observe_bgr, persist_item

    path = root / f"{media_id}.png"
    _write_png(path, image)
    height, width = image.shape[:2]
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        (media_id, "folder", str(path), media_id, int(width), int(height), 0, 1),
    )
    observation_id = f"o-{media_id}"
    conn.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?)",
        (observation_id, media_id, None, None, "r-lens-eval"),
    )
    observe_bgr(
        conn,
        observation_id=observation_id,
        run_id="r-lens-eval",
        img=image,
        observers=("appearance",),
    )
    if text:
        box = text_box or (2, 2, max(8, width - 2), max(8, height // 3))
        persist_item(
            conn,
            observation_id=observation_id,
            run_id="r-lens-eval",
            kind="text",
            provider="tesseract",
            payload={"text": text, "role": "ocr", "contract_status": "SUCCESS"},
            bbox=box,
            score=1.0,
        )
    for label in objects:
        persist_item(
            conn,
            observation_id=observation_id,
            run_id="r-lens-eval",
            kind="object",
            provider=_NANODET,
            payload={"label": label, "class": label, "contract_status": "SUCCESS"},
            bbox=(4, 4, max(12, width - 4), max(12, height - 4)),
            score=0.9,
        )


def build_synthetic_store(root: Path) -> Path:
    """Tiny labelled archive. No faces. No identity embeddings."""
    work = Path(root)
    work.mkdir(parents=True, exist_ok=True)
    store = work / "lens-retrieval.sqlite"
    if store.exists():
        store.unlink()
    conn = connect(store)
    init_db(conn)
    _insert_run(conn)
    red = (20, 20, 200)
    blue = (200, 40, 20)
    grey = (160, 160, 160)
    _add_media(conn, work, "acme-query", _swatch(red), text="ACME coffee", objects=("cup",))
    _add_media(conn, work, "acme-hit", _swatch(red), text="ACME coffee mug", objects=("cup",))
    _add_media(conn, work, "acne-lookalike", _swatch(red), text="ACNE", objects=("cup",))
    _add_media(conn, work, "cup-red", _swatch(red), objects=("cup",))
    _add_media(conn, work, "cup-red-2", _swatch(red), objects=("cup",))
    _add_media(conn, work, "cup-blue", _swatch(blue), objects=("cup",))
    _add_media(conn, work, "chair-red", _swatch(red), objects=("chair",))
    _add_media(
        conn,
        work,
        "shirt-logo",
        _swatch(grey),
        text="ACME",
        objects=("shirt",),
        text_box=(6, 6, 18, 14),
    )
    _add_media(conn, work, "shirt-plain", _swatch(grey), objects=("shirt",))
    _add_media(conn, work, "logo-hit", _swatch(grey), text="ACME", objects=("logo",))
    conn.commit()
    conn.close()
    return store


def _rank_of(ranked: list[str], media_id: str) -> int | None:
    try:
        return ranked.index(media_id) + 1
    except ValueError:
        return None


def relevant_above_hard_neg(
    ranked: list[str],
    relevant: Iterable[str],
    hard_negatives: Iterable[str],
) -> bool:
    """True when the best relevant hit sits above every hard negative."""
    rel_ranks = [rank for mid in relevant if (rank := _rank_of(ranked, mid)) is not None]
    hard_ranks = [rank for mid in hard_negatives if (rank := _rank_of(ranked, mid)) is not None]
    if not rel_ranks:
        return False
    if not hard_ranks:
        return True
    return min(rel_ranks) < min(hard_ranks)


def _region_rec(case: LensCase) -> dict:
    return {
        "status": "SUCCESS",
        "items": [dict(item) for item in case.look_items],
        "similarity_basis": _LOOK_BASIS,
        "engine": "eval-look",
    }


def _crop_for(store: Path, media_id: str):
    conn = connect(store)
    row = conn.execute("SELECT path FROM media WHERE media_id=?", (media_id,)).fetchone()
    conn.close()
    if row is None:
        return np.zeros((16, 16, 3), dtype=np.uint8)
    path = Path(row[0])
    if not path.is_file():
        return np.zeros((16, 16, 3), dtype=np.uint8)
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return np.zeros((16, 16, 3), dtype=np.uint8)
    return image


def _allow_stored_objects():
    """Synthetic labels are already on disk. Do not require the NanoDet weight."""
    from unittest.mock import patch

    return patch("semblon.object_pack.probe_nanodet_status", return_value=(True, "stored labels"))


def run_case(store: Path, case: LensCase) -> dict:
    """Score one labelled highlight through production retrieve_selection."""
    from semblon.selection_retrieval import retrieve_selection

    crop = _crop_for(store, case.query_media_id)
    spec = parse_query_spec(case.query_spec)
    with _allow_stored_objects():
        rec = retrieve_selection(
            store,
            crop=crop,
            observations=[dict(row) for row in case.observations],
            limit=10,
            selection_kind="region",
            query_spec=spec,
            region_rec=_region_rec(case),
            media_id=case.query_media_id,
        )
    ranked = [str(item.get("media_id") or "") for item in rec.get("items") or [] if item.get("media_id")]
    relevant_ranks = {mid: _rank_of(ranked, mid) for mid in case.relevant}
    hard_ranks = {mid: _rank_of(ranked, mid) for mid in case.hard_negatives}
    ahead = relevant_above_hard_neg(ranked, case.relevant, case.hard_negatives)
    return {
        "case_id": case.case_id,
        "family": case.family,
        "status": str(rec.get("status") or "NO_RESULT"),
        "query_spec": spec.as_public(),
        "ranked": ranked,
        "relevant_ranks": relevant_ranks,
        "hard_neg_ranks": hard_ranks,
        "relevant_above_hard_neg": ahead,
        "pass": ahead,
        "channels": [
            {"door": row.get("door"), "status": row.get("status"), "count": row.get("count")}
            for row in rec.get("channels") or []
        ],
        "similarity_basis": rec.get("similarity_basis"),
        "notes": case.notes,
    }


def _precision_block(eval_set: str) -> dict:
    reason = precision_refusal(eval_set)
    return {
        "precision": None,
        "precision_at_5": None,
        "recall_at_5": None,
        "reason": reason,
    }


def score_report(rows: list[dict], *, eval_set: str, elapsed_ms: float, corpus_size: int) -> dict:
    """Assemble the public report. Precision stays None on synthetic."""
    kind = normalize_eval_set(eval_set)
    failures = [row["case_id"] for row in rows if not row.get("pass")]
    seam = index_seam_status()
    precision = _precision_block(kind)
    if kind == EVAL_SET_CONFIRMATORY:
        status = "not_confirmatory"
    else:
        status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "eval_set": kind,
        "method": "retrieve_selection RRF + feature rerank over labelled synthetic tuples",
        "bar": "best relevant rank sits above every hard negative",
        "precision": precision["precision"],
        "precision_at_5": precision["precision_at_5"],
        "recall_at_5": precision["recall_at_5"],
        "precision_reason": precision["reason"],
        "cases": rows,
        "failures": failures,
        "counts": {
            "cases": len(rows),
            "passed": len(rows) - len(failures),
            "failed": len(failures),
            "corpus": corpus_size,
        },
        "timing": {
            "exact_scan_ms": round(float(elapsed_ms), 3),
            "corpus_size": corpus_size,
            "ann_justified": False,
            "ann_reason": (
                "Synthetic corpus is too small to claim an exact-scan bottleneck. "
                "ANN stays parked."
            ),
            "index": seam,
        },
        "identity": {
            "wrote_person_id": False,
            "wrote_face_embedding": False,
            "note": "Region ranking is not identity.",
        },
        "note": (
            "Photographic appearance regression stays docs/evidence/photo-region-eval.json. "
            "This harness does not retune RRF, floors, or S1."
        ),
    }


def _corpus_size(store: Path) -> int:
    conn = connect(store)
    n = int(conn.execute("SELECT COUNT(*) FROM media").fetchone()[0])
    conn.close()
    return n


def identity_clean(store: Path) -> bool:
    """True when the eval store has no person or face-embedding rows."""
    conn = connect(store)
    try:
        persons = int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
        faces = int(conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0])
        face_emb = int(
            conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE modality=?",
                ("face",),
            ).fetchone()[0]
        )
    finally:
        conn.close()
    return persons == 0 and faces == 0 and face_emb == 0


def run_eval(
    root: Path | None = None,
    *,
    eval_set: str = EVAL_SET_SYNTHETIC,
    out: Path | None = None,
) -> dict:
    """Build the synthetic archive, score every labelled case, optionally write JSON."""
    kind = normalize_eval_set(eval_set)
    work = Path(root) if root is not None else Path("docs") / "evidence" / "lens-retrieval-work"
    store = build_synthetic_store(work)
    cases = labelled_cases()
    started = time.perf_counter()
    rows = [run_case(store, case) for case in cases]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if not identity_clean(store):
        raise LensEvalError("eval store wrote identity rows")
    report = score_report(
        rows,
        eval_set=kind,
        elapsed_ms=elapsed_ms,
        corpus_size=_corpus_size(store),
    )
    if out is not None:
        dest = Path(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["out"] = str(dest)
    return report
