"""One-shot People workflow smoke for YuNet+SFace. Not a product CLI."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from pathlib import Path

from semblon.cluster import DEFAULT_EPS, cluster_run
from semblon.engine import PACK_FAMILY, embed_image, load_app
from semblon.ingest import ingest
from semblon.reembed import reembed_stills
from semblon.review import name_cluster, name_face
from semblon.store import connect


def _smoke_image() -> Path:
    env = Path(__import__("os").environ.get("SEMBLON_SMOKE_FACE", "")).expanduser()
    if env.is_file():
        return env
    lena = Path(tempfile.gettempdir()) / "semblon-lena.jpg"
    if not lena.is_file() or lena.stat().st_size < 1000:
        urllib.request.urlretrieve(
            "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
            lena,
        )
    return lena


def main() -> int:
    img = _smoke_image()
    assert img.is_file(), f"missing smoke image: {img}"
    app = load_app()
    faces = embed_image(app, img)
    print("detect", len(faces), "dims", [f["dim"] for f in faces][:8])
    assert faces, "expected at least one face"
    assert all(f["dim"] == 128 for f in faces)

    td = Path(tempfile.mkdtemp(prefix="ys-people-"))
    media = td / "media"
    media.mkdir()
    import cv2
    import numpy as np

    raw = cv2.imread(str(img))
    assert raw is not None
    for i in range(3):
        # Distinct bytes so ingest does not hash-skip copies.
        frame = raw.copy()
        frame[0, i, :] = (i * 40) % 256
        cv2.imwrite(str(media / f"p{i}.jpg"), frame)
    store = td / "store.sqlite"
    rec = ingest(media, store, reprocess=True)
    print(
        "ingest",
        {
            "faces": rec.get("faces"),
            "ok": rec.get("ok"),
            "pack_id": rec.get("pack_id"),
        },
    )
    assert "opencv/yunet_sface" in str(rec.get("pack_id"))
    assert int(rec.get("faces") or 0) >= 1

    clu = cluster_run(store, rec["run_id"], eps=DEFAULT_EPS)
    print(
        "cluster",
        {
            k: clu.get(k)
            for k in ("clusters", "clustered", "unassigned", "ok_faces", "eps")
        },
    )
    conn = connect(store)
    row = conn.execute(
        """SELECT cluster_id, count(*) AS c FROM faces
           WHERE status='ok' AND cluster_id IS NOT NULL
           GROUP BY cluster_id ORDER BY c DESC"""
    ).fetchone()
    if row is not None:
        named = name_cluster(store, rec["run_id"], row["cluster_id"], "Smoke Person")
        print("named_cluster", named.get("person_id"), named.get("display_name"))
    else:
        # Provisional SFace eps may leave copies unassigned; prove review via name_face.
        top = conn.execute(
            """SELECT face_id FROM faces WHERE status='ok'
               ORDER BY det_score DESC LIMIT 1"""
        ).fetchone()
        assert top is not None, "expected an ok face for naming"
        named = name_face(store, rec["run_id"], top["face_id"], "Smoke Person")
        print("named_face", named.get("person_id"), named.get("display_name"))
        print(
            "note",
            "cluster empty at provisional eps — Q-gate calibration still OPEN",
        )

    n_named = conn.execute(
        "SELECT count(*) AS c FROM faces WHERE person_id IS NOT NULL"
    ).fetchone()["c"]
    print("faces_with_person", n_named)
    assert n_named >= 1

    r2 = reembed_stills(store, resume=False, clear_clusters=True)
    print(
        "reembed",
        {k: r2[k] for k in ("status", "faces_written", "faces_ok", "pack_id")},
    )
    assert r2["status"] == "SUCCESS"
    print("PACK_FAMILY", PACK_FAMILY)
    print("OK_PEOPLE_WORKFLOW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
