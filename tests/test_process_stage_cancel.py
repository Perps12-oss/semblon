"""Item 03 — cancel is polled before cluster and before export."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from semblon.process import ProcessCancelled, process_folder


def test_cancel_after_ingest_skips_cluster_and_export(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"

    def cancel() -> bool:
        return True

    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "RUN-C",
                "new_media": 1,
                "faces": 4,
                "ok": 4,
                "skipped_seen": 0,
            },
        ),
        patch("semblon.process.cluster_run") as clu,
        patch("semblon.process.export_review") as exp,
        patch("semblon.process.persist_run_stage"),
    ):
        with pytest.raises(ProcessCancelled) as ei:
            process_folder(
                folder,
                store=store,
                out=out,
                open_review=False,
                progress=lambda *_: None,
                cancel=cancel,
            )
    assert ei.value.run_id == "RUN-C"
    clu.assert_not_called()
    exp.assert_not_called()


def test_cancel_after_cluster_skips_export(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    store = tmp_path / "store.sqlite"
    out = tmp_path / "review.html"
    state = {"after_cluster": False}

    def cancel() -> bool:
        return state["after_cluster"]

    def fake_cluster(*_args, **_kwargs):
        state["after_cluster"] = True
        return {"clusters": 1, "clustered": 2, "unassigned": 0}

    with (
        patch(
            "semblon.process.ingest",
            return_value={
                "run_id": "RUN-E",
                "new_media": 1,
                "faces": 2,
                "ok": 2,
                "skipped_seen": 0,
            },
        ),
        patch("semblon.process.cluster_run", side_effect=fake_cluster) as clu,
        patch("semblon.process.export_review") as exp,
        patch("semblon.process.persist_run_stage"),
    ):
        with pytest.raises(ProcessCancelled) as ei:
            process_folder(
                folder,
                store=store,
                out=out,
                open_review=False,
                progress=lambda *_: None,
                cancel=cancel,
            )
    assert ei.value.run_id == "RUN-E"
    clu.assert_called_once()
    exp.assert_not_called()
