"""FACE-002: confirmatory eval harness.

Precision is printed only on a frozen confirmatory set.
Underpowered is a first-class result — do not invent FAR/FRR.
Mined discovery is not confirmatory. Remine never writes confirmatory rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.cluster import DEFAULT_EPS
from semblon.compare import CompareError, compare
from semblon.export import STRONG_MIN_INTRA
from semblon.store import connect, init_db

KINDS = (
    "confirmatory_hard",
    "mined_discovery",
    "soft_impostor",
    "genuine",
)
CONFIRMATORY = "confirmatory_hard"
# Keep-together boundary tracks active cluster DEFAULT_EPS (SFace provisional).
DEFAULT_THRESHOLD = round(1.0 - DEFAULT_EPS, 2)
HARD_NEAR = STRONG_MIN_INTRA
MIN_SAME = 10
MIN_DIFFERENT = 10
DEFAULT_MINE_MAX = 50


class EvalError(ValueError):
    pass


def _open(store: Path, readonly: bool = False):
    p = Path(store)
    if readonly:
        if not p.is_file():
            raise EvalError(f"store not found: {p}")
        conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    conn = connect(p)
    init_db(conn)
    return conn


def _require_set(conn, eval_set_id: str):
    row = conn.execute(
        "SELECT * FROM eval_sets WHERE eval_set_id=?", (eval_set_id,)
    ).fetchone()
    if row is None:
        raise EvalError(f"unknown eval set: {eval_set_id}")
    return row


def _canon(face_a: str, face_b: str) -> tuple[str, str]:
    if face_a == face_b:
        raise EvalError("pair must be two distinct faces")
    return (face_a, face_b) if face_a < face_b else (face_b, face_a)


def resolve_eval_set_id(conn, eval_set_id: str) -> str:
    """`confirmatory` means the single frozen confirmatory_hard set."""
    if eval_set_id != "confirmatory":
        return eval_set_id
    rows = conn.execute(
        """SELECT eval_set_id FROM eval_sets
           WHERE kind=? AND frozen=1 ORDER BY eval_set_id""",
        (CONFIRMATORY,),
    ).fetchall()
    if not rows:
        raise EvalError("no frozen confirmatory eval set")
    if len(rows) > 1:
        raise EvalError("ambiguous confirmatory: more than one frozen confirmatory_hard set")
    return rows[0][0]


def create_set(
    store: Path,
    eval_set_id: str,
    kind: str,
    pack_id: str | None = None,
    notes: str | None = None,
) -> dict:
    if kind not in KINDS:
        raise EvalError(f"unknown kind: {kind}")
    if not eval_set_id or eval_set_id.lower() == "confirmatory":
        raise EvalError("eval_set id is required")
    conn = _open(store)
    exists = conn.execute(
        "SELECT 1 FROM eval_sets WHERE eval_set_id=?", (eval_set_id,)
    ).fetchone()
    if exists:
        conn.close()
        raise EvalError(f"eval set already exists: {eval_set_id}")
    conn.execute(
        "INSERT INTO eval_sets(eval_set_id, kind, frozen, pack_id, notes) VALUES (?,?,?,?,?)",
        (eval_set_id, kind, 0, pack_id, notes or ""),
    )
    conn.commit()
    conn.close()
    return {
        "eval_set_id": eval_set_id,
        "kind": kind,
        "frozen": 0,
        "pack_id": pack_id,
        "notes": notes or "",
    }


def add_pair(
    store: Path,
    eval_set_id: str,
    face_a: str,
    face_b: str,
    label: str,
    stratum: str,
) -> dict:
    if label not in ("same", "different"):
        raise EvalError("label must be same or different")
    if not stratum:
        raise EvalError("stratum is required")
    a, b = _canon(face_a, face_b)
    conn = _open(store)
    eset = _require_set(conn, eval_set_id)
    if eset["frozen"]:
        conn.close()
        raise EvalError("eval set is frozen (immutable)")
    for fid in (a, b):
        if conn.execute("SELECT 1 FROM faces WHERE face_id=?", (fid,)).fetchone() is None:
            conn.close()
            raise EvalError(f"unknown face: {fid}")
    existing = conn.execute(
        "SELECT 1 FROM eval_pairs WHERE eval_set_id=? AND face_a=? AND face_b=?",
        (eval_set_id, a, b),
    ).fetchone()
    if existing is not None:
        conn.close()
        raise EvalError(f"pair already in set: {a} {b}")
    try:
        conn.execute(
            """INSERT INTO eval_pairs(eval_set_id, face_a, face_b, label, stratum)
               VALUES (?,?,?,?,?)""",
            (eval_set_id, a, b, label, stratum),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise EvalError(f"invalid pair or eval set for insert: {a} {b}") from e
    conn.close()
    return {
        "eval_set_id": eval_set_id,
        "face_a": a,
        "face_b": b,
        "label": label,
        "stratum": stratum,
    }


def freeze_set(store: Path, eval_set_id: str) -> dict:
    conn = _open(store)
    eset = _require_set(conn, eval_set_id)
    if not eset["frozen"]:
        conn.execute(
            "UPDATE eval_sets SET frozen=1 WHERE eval_set_id=?", (eval_set_id,)
        )
        conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM eval_pairs WHERE eval_set_id=?", (eval_set_id,)
    ).fetchone()[0]
    conn.close()
    return {"eval_set_id": eval_set_id, "kind": eset["kind"], "frozen": 1, "pairs": n}


def mine_discovery(
    store: Path,
    run_id: str,
    eval_set_id: str,
    *,
    min_sim: float = HARD_NEAR,
    max_pairs: int = DEFAULT_MINE_MAX,
) -> dict:
    """Write hypothesized different-cluster lookalikes into a mined_discovery set.

    Never writes confirmatory rows. Remine replaces only this set's pairs.
    """
    conn = _open(store)
    eset = _require_set(conn, eval_set_id)
    if eset["kind"] != "mined_discovery":
        conn.close()
        raise EvalError("remine does not write confirmatory (or other) sets")
    if eset["frozen"]:
        conn.close()
        raise EvalError("eval set is frozen (immutable)")
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        raise EvalError(f"unknown run: {run_id}")
    pack_id = eset["pack_id"] or run["pack_id"]
    rows = conn.execute(
        """
        SELECT face_id, cluster_id, embedding, embedding_pack, embedding_dim
        FROM faces
        WHERE run_id=? AND status='ok' AND embedding IS NOT NULL
          AND cluster_id IS NOT NULL
          AND embedding_pack=?
        ORDER BY face_id
        """,
        (run_id, pack_id),
    ).fetchall()
    faces = rows
    candidates: list[tuple[float, str, str]] = []
    for i, a in enumerate(faces):
        for b in faces[i + 1 :]:
            if a["cluster_id"] == b["cluster_id"]:
                continue
            try:
                s = compare(
                    pack_id,
                    a["embedding_dim"],
                    a["embedding"],
                    pack_id,
                    b["embedding_dim"],
                    b["embedding"],
                )
            except CompareError:
                continue
            if s >= min_sim:
                fa, fb = _canon(a["face_id"], b["face_id"])
                candidates.append((float(s), fa, fb))
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    picked = candidates[: max(0, int(max_pairs))]
    with conn:
        conn.execute("DELETE FROM eval_pairs WHERE eval_set_id=?", (eval_set_id,))
        for _s, fa, fb in picked:
            conn.execute(
                """INSERT INTO eval_pairs(eval_set_id, face_a, face_b, label, stratum)
                   VALUES (?,?,?,?,?)""",
                (eval_set_id, fa, fb, "different", "mined"),
            )
    conn.close()
    return {
        "eval_set_id": eval_set_id,
        "kind": "mined_discovery",
        "run_id": run_id,
        "pack_id": pack_id,
        "min_sim": min_sim,
        "candidates": len(candidates),
        "pairs": len(picked),
        "frozen": 0,
    }


def _score_pair(conn, eset, face_a: str, face_b: str, threshold: float, face_cache: dict[str, sqlite3.Row] | None = None) -> dict:
    cache = face_cache if face_cache is not None else {}
    a = cache.get(face_a)
    if a is None and face_a not in cache:
        a = conn.execute("SELECT * FROM faces WHERE face_id=?", (face_a,)).fetchone()
        cache[face_a] = a
    b = cache.get(face_b)
    if b is None and face_b not in cache:
        b = conn.execute("SELECT * FROM faces WHERE face_id=?", (face_b,)).fetchone()
        cache[face_b] = b
    out = {
        "face_a": face_a,
        "face_b": face_b,
        "similarity": None,
        "decision": "skip",
        "cluster_a": None if a is None else a["cluster_id"],
        "cluster_b": None if b is None else b["cluster_id"],
        "skip_reason": None,
    }
    if a is None or b is None:
        out["skip_reason"] = "missing_face"
        return out
    if a["status"] != "ok" or b["status"] != "ok":
        out["skip_reason"] = "not_ok"
        return out
    if a["embedding"] is None or b["embedding"] is None:
        out["skip_reason"] = "no_embedding"
        return out
    pack = eset["pack_id"]
    if pack and (a["embedding_pack"] != pack or b["embedding_pack"] != pack):
        out["skip_reason"] = "pack_mismatch"
        return out
    try:
        sim = compare(
            a["embedding_pack"],
            a["embedding_dim"],
            a["embedding"],
            b["embedding_pack"],
            b["embedding_dim"],
            b["embedding"],
        )
    except CompareError as e:
        out["skip_reason"] = str(e)
        return out
    out["similarity"] = float(sim)
    out["decision"] = "accept" if sim >= threshold else "reject"
    out["skip_reason"] = None
    return out


def score_set(
    store: Path | None,
    eval_set_id: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    conn=None,
) -> dict:
    """Score pairs. FAR/FRR only for a frozen confirmatory_hard set that is powered."""
    own = conn is None
    if own:
        conn = _open(store, readonly=True)
    try:
        eval_set_id = resolve_eval_set_id(conn, eval_set_id)
        eset = _require_set(conn, eval_set_id)
        pairs = conn.execute(
            """SELECT face_a, face_b, label, stratum FROM eval_pairs
               WHERE eval_set_id=? ORDER BY face_a, face_b""",
            (eval_set_id,),
        ).fetchall()
        scored_rows = []
        n_same = n_diff = 0
        n_same_scored = n_diff_scored = 0
        n_scored = n_skipped = 0
        n_fa = n_fr = 0
        n_hard = 0
        n_impure = 0
        skip_reasons: dict[str, int] = {}
        face_cache: dict[str, sqlite3.Row | None] = {}
        for p in pairs:
            if p["label"] == "same":
                n_same += 1
            else:
                n_diff += 1
            rec = _score_pair(conn, eset, p["face_a"], p["face_b"], threshold, face_cache)
            rec["label"] = p["label"]
            rec["stratum"] = p["stratum"]
            if rec["decision"] == "skip":
                n_skipped += 1
                reason = rec.get("skip_reason") or "unknown"
                skip_reasons[reason] = int(skip_reasons.get(reason, 0)) + 1
            else:
                n_scored += 1
                if p["label"] == "same":
                    n_same_scored += 1
                    if rec["decision"] == "reject":
                        n_fr += 1
                else:
                    n_diff_scored += 1
                    if rec["decision"] == "accept":
                        n_fa += 1
                if (
                    p["label"] == "different"
                    and rec["similarity"] is not None
                    and rec["similarity"] >= HARD_NEAR
                ):
                    n_hard += 1
            if (
                p["label"] == "different"
                and rec["cluster_a"]
                and rec["cluster_a"] == rec["cluster_b"]
            ):
                n_impure += 1
            scored_rows.append(rec)

        confirmatory = eset["kind"] == CONFIRMATORY
        frozen = bool(eset["frozen"])
        reasons: list[str] = []
        if not confirmatory:
            reasons.append("not confirmatory — precision refused")
        if confirmatory and not frozen:
            reasons.append("confirmatory set is not frozen")
        if confirmatory and frozen:
            if n_same_scored < MIN_SAME:
                reasons.append(
                    f"underpowered same pairs ({n_same_scored} scored < {MIN_SAME})"
                )
            if n_diff_scored < MIN_DIFFERENT:
                reasons.append(
                    f"underpowered different pairs ({n_diff_scored} scored < {MIN_DIFFERENT})"
                )
            if n_hard < 1:
                reasons.append("underpowered: no hard-negative pair near the identity boundary")

        if confirmatory and frozen and not reasons:
            status = "measurable"
            # Skipped pairs are not trials. They must not dilute FAR/FRR.
            far = (n_fa / n_diff_scored) if n_diff_scored else None
            frr = (n_fr / n_same_scored) if n_same_scored else None
        elif confirmatory:
            status = "underpowered"
            far = None
            frr = None
        else:
            status = "not_confirmatory"
            far = None
            frr = None

        return {
            "eval_set_id": eval_set_id,
            "kind": eset["kind"],
            "frozen": int(eset["frozen"]),
            "pack_id": eset["pack_id"],
            "threshold": threshold,
            "hard_near": HARD_NEAR,
            "status": status,
            "reason": "; ".join(reasons) if reasons else None,
            "counts": {
                "pairs": len(pairs),
                "same": n_same,
                "different": n_diff,
                "same_scored": n_same_scored,
                "different_scored": n_diff_scored,
                "scored": n_scored,
                "skipped": n_skipped,
                "false_accept": n_fa,
                "false_reject": n_fr,
                "hard_negatives": n_hard,
                "cluster_impurity": n_impure,
                "skip_reasons": skip_reasons,
            },
            "far": far,
            "frr": frr,
            "fnmr": frr,
            "pairs": scored_rows,
        }
    finally:
        if own:
            conn.close()


def accuracy_board(conn) -> dict:
    """Observatory accuracy slice. Read-only. Never invents FAR/FRR."""
    rows = conn.execute(
        """SELECT eval_set_id FROM eval_sets
           WHERE kind=? AND frozen=1 ORDER BY eval_set_id""",
        (CONFIRMATORY,),
    ).fetchall()
    if not rows:
        return {
            "status": "not_measurable",
            "reason": "no frozen confirmatory eval_set",
        }
    reports = [score_set(None, r[0], conn=conn) for r in rows]
    measurable = [r for r in reports if r["status"] == "measurable"]
    if measurable:
        best = measurable[0]
        return {
            "status": "measurable",
            "reason": None,
            "eval_set_id": best["eval_set_id"],
            "far": best["far"],
            "frr": best["frr"],
            "fnmr": best["fnmr"],
            "threshold": best["threshold"],
            "counts": best["counts"],
        }
    first = reports[0]
    return {
        "status": "underpowered",
        "reason": first["reason"] or "frozen confirmatory set is underpowered",
        "eval_set_id": first["eval_set_id"],
        "far": None,
        "frr": None,
        "fnmr": None,
        "threshold": first["threshold"],
        "counts": first["counts"],
    }
