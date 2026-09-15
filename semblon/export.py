"""0.3 export: static review.html. Read-only. No server."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import sqlite3

from semblon.compare import CompareError, compare

EVIDENCE_SCHEMA = "1"
EVIDENCE_SCRIPT_ID = "semblon-run-evidence"

# Hypothesis — clusters with min_intra below this are REVIEW REQUIRED.
STRONG_MIN_INTRA = 0.50
THUMB_MAX = 96
WORST_MAX = 160


class ExportError(ValueError):
    pass


def _esc(s) -> str:
    return html.escape("" if s is None else str(s))


def _stored_json(raw):
    """Parse a SQLite JSON column only when it is valid JSON. No other rewrite."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    if not isinstance(raw, str):
        return raw
    if raw == "":
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _decision_public(row) -> dict:
    return {
        "kind": row["kind"],
        "cluster_id": row["cluster_id"],
        "face_id": row["face_id"],
        "created_at": row["created_at"],
        "policy": _stored_json(row["policy_json"]),
    }


def _evidence_payload(run, clusters, counts: dict, strong_min_intra: float, decisions=()) -> dict:
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "run_id": run["run_id"],
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "software_version": run["software_version"],
        "pack_id": run["pack_id"],
        "embedding_dim": run["embedding_dim"],
        "embedding_norm": run["embedding_norm"],
        "config_json": _stored_json(run["config_json"]),
        "runtime_json": _stored_json(run["runtime_json"]),
        "arch": run["arch"],
        "execution": run["execution"],
        "ort_version": run["ort_version"],
        "peak_rss_mb": run["peak_rss_mb"],
        "timings_json": _stored_json(run["timings_json"]),
        "strong_min_intra": strong_min_intra,
        "counts": counts,
        "clusters": [
            {
                "cluster_id": c["cluster_id"],
                "strategy": c["strategy"],
                "face_count": c["face_count"],
                "min_intra": c["min_intra"],
                "status": c["status"],
            }
            for c in clusters
        ],
        "decisions": [_decision_public(d) for d in decisions],
    }


def _evidence_script(payload: dict) -> str:
    # Neutralize </script so a stored path cannot close the tag. \/ is valid JSON.
    body = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    return f'<script type="application/json" id="{EVIDENCE_SCRIPT_ID}">{body}</script>'


def _file_uri(path: str) -> str:
    try:
        return Path(path).resolve().as_uri()
    except OSError:
        return Path(path).as_uri() if path else ""


def _crop_jpeg(path: str, bbox, max_side: int) -> str | None:
    try:
        import cv2
    except ImportError:
        return None
    img = cv2.imread(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    pad = int(0.08 * max(x2 - x1, y2 - y1, 1))
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]
    scale = max_side / max(ch, cw, 1)
    if scale < 1:
        crop = cv2.resize(
            crop,
            (max(1, int(cw * scale)), max(1, int(ch * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not ok:
        return None
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _img_tag(data_uri: str | None, path: str, face_id: str, cls: str) -> str:
    href = _file_uri(path) if path else ""
    alt = _esc(face_id)
    if data_uri:
        img = f'<img class="{cls}" src="{data_uri}" alt="{alt}">'
    else:
        img = f'<span class="missing">{alt}</span>'
    if href:
        return f'<a href="{_esc(href)}">{img}</a>'
    return img


def _worst_pair(members, pack_id: str):
    best = None
    pair = None
    for i, a in enumerate(members):
        if a["embedding"] is None:
            continue
        for b in members[i + 1 :]:
            if b["embedding"] is None:
                continue
            if a["embedding_pack"] != pack_id or b["embedding_pack"] != pack_id:
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
            if best is None or s < best:
                best = float(s)
                pair = (a, b)
    return best, pair


def _load(conn, run_id: str):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise ExportError(f"unknown run: {run_id}")
    clusters = conn.execute(
        """SELECT * FROM clusters WHERE run_id=? ORDER BY min_intra ASC, face_count DESC""",
        (run_id,),
    ).fetchall()
    faces = conn.execute(
        """
        SELECT f.*, m.path
        FROM faces f
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.run_id=?
        ORDER BY f.face_id
        """,
        (run_id,),
    ).fetchall()
    decisions = conn.execute(
        """SELECT * FROM decisions WHERE run_id=? ORDER BY created_at, decision_id""",
        (run_id,),
    ).fetchall()
    return run, clusters, faces, decisions


def _face_dict(row) -> dict:
    return {
        "face_id": row["face_id"],
        "path": row["path"],
        "status": row["status"],
        "det_score": row["det_score"],
        "face_w": row["face_w"],
        "face_h": row["face_h"],
        "cluster_id": row["cluster_id"],
        "bbox": (row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]),
        "embedding": row["embedding"],
        "embedding_pack": row["embedding_pack"],
        "embedding_dim": row["embedding_dim"],
    }


def _render_cluster(c, members, pack_id: str, kind: str) -> str:
    min_intra = c["min_intra"]
    intra_s = "\u2014" if min_intra is None else f"{min_intra:.3f}"
    sim, pair = _worst_pair(members, pack_id)
    parts = [
        f'<article class="cluster {kind}" id="c-{_esc(c["cluster_id"])}">',
        f'<h3>cluster {_esc(c["cluster_id"][:8])} \u00b7 {c["face_count"]} faces \u00b7 min_intra {intra_s}</h3>',
        f'<p class="meta">strategy {_esc(c["strategy"])} \u00b7 status {_esc(c["status"])} \u00b7 not a person</p>',
    ]
    if pair is not None and sim is not None:
        a, b = pair
        parts.append(
            f'<div class="worst"><p>worst pair similarity {sim:.3f}</p>'
            f'{_img_tag(_crop_jpeg(a["path"], a["bbox"], WORST_MAX), a["path"], a["face_id"], "worstimg")}'
            f'{_img_tag(_crop_jpeg(b["path"], b["bbox"], WORST_MAX), b["path"], b["face_id"], "worstimg")}'
            f"</div>"
        )
    parts.append('<div class="thumbs">')
    for m in members:
        parts.append(
            _img_tag(_crop_jpeg(m["path"], m["bbox"], THUMB_MAX), m["path"], m["face_id"], "thumb")
        )
    parts.append("</div></article>")
    return "\n".join(parts)


def _render_faces(title: str, anchor: str, rows: list[dict]) -> str:
    parts = [
        f'<section id="{anchor}">',
        f"<h2>{_esc(title)} ({len(rows)})</h2>",
        '<div class="thumbs">',
    ]
    for m in rows:
        label = f'{m["face_id"][:8]} {m["status"]} {m["face_w"]}x{m["face_h"]}'
        parts.append(
            "<figure>"
            + _img_tag(_crop_jpeg(m["path"], m["bbox"], THUMB_MAX), m["path"], m["face_id"], "thumb")
            + f"<figcaption>{_esc(label)}</figcaption></figure>"
        )
    if not rows:
        parts.append("<p>none</p>")
    parts.append("</div></section>")
    return "\n".join(parts)


def _render_decisions(decisions) -> str:
    parts = ['<section id="decisions">', f"<h2>DECISIONS ({len(decisions)})</h2>"]
    parts.append(
        '<p class="meta">Human review. Merge does not create a person. '
        "rejected / low_quality stay held-out.</p>"
    )
    if not decisions:
        parts.append("<p>none</p></section>")
        return "\n".join(parts)
    parts.append("<ol>")
    for d in decisions:
        pol = _stored_json(d["policy_json"])
        if not isinstance(pol, dict):
            pol = {"raw": pol}
        action = pol.get("action") or d["kind"]
        disp = pol.get("disposition") or pol.get("text") or ""
        target = d["cluster_id"] or d["face_id"] or ""
        parts.append(
            "<li>"
            f"<strong>{_esc(d['kind'])}</strong>"
            f" {_esc(action)}"
            f" {_esc(disp)}"
            f" {_esc(target[:12] if target else '')}"
            f" <span class=\"meta\">{_esc(d['created_at'])}</span>"
            "</li>"
        )
    parts.append("</ol></section>")
    return "\n".join(parts)


def render_review_html(
    run,
    clusters,
    faces,
    strong_min_intra: float = STRONG_MIN_INTRA,
    decisions=(),
) -> str:
    pack_id = run["pack_id"]
    by_cluster: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    rejected: list[dict] = []
    for raw in faces:
        d = _face_dict(raw)
        if d["status"] == "rejected":
            rejected.append(d)
        elif d["cluster_id"]:
            by_cluster.setdefault(d["cluster_id"], []).append(d)
        elif d["status"] == "ok":
            # Same eligibility as cluster CLI: only OK faces can be unassigned.
            unassigned.append(d)

    review_cs = []
    strong_cs = []
    for c in clusters:
        members = by_cluster.get(c["cluster_id"], [])
        mi = c["min_intra"]
        if mi is None or mi < strong_min_intra:
            review_cs.append((c, members))
        else:
            strong_cs.append((c, members))

    review_cs.sort(key=lambda x: (x[0]["min_intra"] is None, x[0]["min_intra"] if x[0]["min_intra"] is not None else 0.0))
    strong_cs.sort(key=lambda x: (-(x[0]["min_intra"] or 0.0), -x[0]["face_count"]))

    n_ok = sum(1 for f in faces if f["status"] == "ok")
    n_lq = sum(1 for f in faces if f["status"] == "low_quality")
    n_rej = len(rejected)
    timings = run["timings_json"] or ""
    counts = {
        "faces": len(faces),
        "ok": n_ok,
        "low_quality": n_lq,
        "rejected": n_rej,
        "clusters": len(clusters),
        "review_required": len(review_cs),
        "strong": len(strong_cs),
        "unassigned": len(unassigned),
        "decisions": len(decisions),
    }
    evidence = _evidence_script(
        _evidence_payload(run, clusters, counts, strong_min_intra, decisions)
    )

    body_clusters_review = "\n".join(
        _render_cluster(c, m, pack_id, "review") for c, m in review_cs
    ) or "<p>none</p>"
    body_clusters_strong = "\n".join(
        _render_cluster(c, m, pack_id, "strong") for c, m in strong_cs
    ) or "<p>none</p>"

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Semblon review — {_esc(run["run_id"])}</title>
<style>
body {{ font-family: sans-serif; margin: 1rem; background: #111; color: #eee; }}
a {{ color: #9cf; }}
h1,h2,h3 {{ font-weight: 600; }}
.counts span {{ display: inline-block; margin: 0 .8rem .4rem 0; }}
nav a {{ margin-right: 1rem; }}
article.cluster {{ border: 1px solid #444; padding: .75rem; margin: .75rem 0; }}
article.review {{ border-color: #a63; }}
article.strong {{ border-color: #385; }}
.thumbs {{ display: flex; flex-wrap: wrap; gap: .4rem; align-items: flex-start; }}
img.thumb, img.worstimg {{ display: block; background: #222; }}
.worst {{ margin: .5rem 0; display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }}
.meta, figcaption {{ color: #aaa; font-size: .8rem; }}
.missing {{ display: inline-block; width: 6rem; height: 6rem; background: #333; font-size: .7rem; padding: .3rem; }}
</style>
</head>
<body>
<h1>Semblon review</h1>
<p class="counts">
  <span>run <strong>{_esc(run["run_id"])}</strong></span>
  <span>pack_id {_esc(pack_id)}</span>
  <span>arch {_esc(run["arch"])} {_esc(run["execution"])}</span>
</p>
<p class="counts">
  <span>faces {len(faces)}</span>
  <span>ok {n_ok}</span>
  <span>low_quality {n_lq}</span>
  <span>rejected {n_rej}</span>
  <span>clusters {len(clusters)}</span>
  <span>REVIEW REQUIRED {len(review_cs)}</span>
  <span>STRONG {len(strong_cs)}</span>
  <span>UNASSIGNED {len(unassigned)}</span>
  <span>DECISIONS {len(decisions)}</span>
</p>
<p class="meta">cluster → review → person → name. Clusters are not persons.
STRONG means min_intra ≥ {strong_min_intra:.2f} (hypothesis). Open originals via the thumbnails.
timings { _esc(timings) }</p>
<nav>
  <a href="#review">REVIEW REQUIRED</a>
  <a href="#strong">STRONG</a>
  <a href="#unassigned">UNASSIGNED</a>
  <a href="#rejected">REJECTED</a>
  <a href="#decisions">DECISIONS</a>
</nav>

<section id="review">
<h2>REVIEW REQUIRED ({len(review_cs)})</h2>
<p class="meta">Worst min_intra first. Mixed groups belong here.</p>
{body_clusters_review}
</section>

<section id="strong">
<h2>STRONG ({len(strong_cs)})</h2>
<p class="meta">Tight groups. Still not persons until named in 0.4.</p>
{body_clusters_strong}
</section>

{_render_faces("UNASSIGNED", "unassigned", unassigned)}
{_render_faces("REJECTED", "rejected", rejected)}
{_render_decisions(decisions)}
</body>
</html>
"""
    return page.replace("</body>", evidence + "\n</body>", 1)


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise ExportError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def export_review(
    store: Path,
    run_id: str,
    out: Path,
    strong_min_intra: float = STRONG_MIN_INTRA,
) -> dict:
    conn = _connect_ro(store)
    run, clusters, faces, decisions = _load(conn, run_id)
    html_text = render_review_html(
        run, clusters, faces, strong_min_intra=strong_min_intra, decisions=decisions
    )
    conn.close()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    return {
        "run_id": run_id,
        "out": str(out.resolve()),
        "clusters": len(clusters),
        "faces": len(faces),
        "bytes": out.stat().st_size,
    }
