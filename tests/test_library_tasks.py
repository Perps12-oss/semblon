"""The library tray names real work and stays clickable when nothing is running."""

from semblon.library_tasks import library_work


def _snap(**kwargs):
    base = {
        "library_count": 12,
        "job_active": False,
        "job_state": "idle",
        "job_current": 0,
        "job_total": 0,
        "can_resume": False,
        "last_failed": False,
        "has_folder": True,
        "search_busy": False,
        "index_state": "",
        "index_note": "",
        "library_summary": "12 photos. Originals stay where they are.",
    }
    base.update(kwargs)
    return base


def test_quiet_library_is_a_state_with_one_next_action():
    work = library_work(_snap())
    assert work["quiet"] is True
    assert work["count"] == 0
    assert work["label"] == "Quiet"
    assert work["rows"][0]["id"] == "quiet"
    assert work["rows"][0]["counts"] is False
    assert "Nothing is scanning" in work["summary"]
    assert work["rows"][0]["actions"] == [{"id": "rescan", "label": "Check for new files"}]


def test_empty_library_offers_add_folder():
    work = library_work(_snap(library_count=0, has_folder=False, library_summary=""))
    assert work["label"] == "Quiet"
    assert work["rows"][0]["actions"][0]["id"] == "add-folder"
    assert "No folder" in work["summary"]


def test_running_add_and_search_are_two_tasks():
    work = library_work(
        _snap(job_active=True, job_state="running", job_current=2, job_total=9, search_busy=True)
    )
    assert work["count"] == 2
    assert work["label"] == "2 tasks"
    assert work["quiet"] is False
    assert work["rows"][0]["id"] == "ingest"
    assert "2 of 9" in work["rows"][0]["detail"]
    assert [item["id"] for item in work["rows"][0]["actions"]] == ["pause", "cancel"]
    assert work["rows"][1]["actions"][0]["id"] == "cancel-search"


def test_paused_add_offers_resume_and_hides_the_quiet_row():
    work = library_work(_snap(job_active=True, job_state="paused", job_current=1, job_total=4))
    assert work["count"] == 1
    assert work["label"] == "1 task"
    assert work["rows"][0]["title"] == "Adding photos is paused"
    assert [item["id"] for item in work["rows"][0]["actions"]] == ["resume", "cancel"]
    assert all(row["id"] != "quiet" for row in work["rows"])


def test_stopped_add_is_a_task_until_it_is_resumed():
    work = library_work(_snap(can_resume=True, last_failed=True))
    assert work["count"] == 1
    assert work["rows"][0]["id"] == "resume-add"
    assert work["rows"][0]["actions"][0]["id"] == "resume"


def test_failed_add_offers_another_look_at_the_folder():
    work = library_work(_snap(last_failed=True))
    assert work["rows"][0]["id"] == "failed-add"
    assert work["rows"][0]["actions"][0] == {"id": "rescan", "label": "Try again"}


def test_unindexed_photo_is_work_when_nothing_else_is_running():
    work = library_work(
        _snap(index_state="unindexed", index_note="This photo is not indexed yet.")
    )
    assert work["count"] == 1
    assert work["rows"][0]["title"] == "This photo is not indexed"
    assert "not indexed yet" in work["rows"][0]["detail"]


def test_an_active_add_covers_the_unindexed_note():
    work = library_work(_snap(job_active=True, job_state="running", index_state="unindexed"))
    assert [row["id"] for row in work["rows"]] == ["ingest"]
