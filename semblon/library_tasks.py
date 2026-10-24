"""Library work the shell can show without covering the timeline.

The tray is a view of work that already exists: an add in progress, a search,
a stopped add, or a photo that was never indexed. A quiet library is a real
state with one next action. This module does not start jobs and does not
read the store.
"""

from __future__ import annotations


def library_work(snapshot: dict) -> dict:
    """Turn a shell snapshot into the pill label and the rows behind it."""
    library_count = int(snapshot.get("library_count") or 0)
    job_active = bool(snapshot.get("job_active"))
    job_state = str(snapshot.get("job_state") or "idle")
    current = int(snapshot.get("job_current") or 0)
    total = int(snapshot.get("job_total") or 0)
    can_resume = bool(snapshot.get("can_resume")) and not job_active
    last_failed = bool(snapshot.get("last_failed")) and not job_active and not can_resume
    has_folder = bool(snapshot.get("has_folder"))
    search_busy = bool(snapshot.get("search_busy"))
    index_state = str(snapshot.get("index_state") or "")
    index_note = str(snapshot.get("index_note") or "").strip()
    library_summary = str(snapshot.get("library_summary") or "").strip()

    rows: list[dict] = []
    if job_active:
        if job_state == "paused":
            title = "Adding photos is paused"
            actions = [
                {"id": "resume", "label": "Resume"},
                {"id": "cancel", "label": "Cancel"},
            ]
        elif job_state == "cancelling":
            title = "Stopping the add"
            actions = []
        else:
            title = "Adding photos"
            actions = [
                {"id": "pause", "label": "Pause"},
                {"id": "cancel", "label": "Cancel"},
            ]
        if total > 0:
            detail = f"{current} of {total}. Photos already added can be opened."
        else:
            detail = "Photos already added can be opened."
        rows.append(
            {
                "id": "ingest",
                "title": title,
                "detail": detail,
                "actions": actions,
                "counts": True,
            }
        )
    if search_busy:
        rows.append(
            {
                "id": "search",
                "title": "Looking through photos",
                "detail": "The library stays open while this search finishes.",
                "actions": [{"id": "cancel-search", "label": "Cancel search"}],
                "counts": True,
            }
        )
    if can_resume:
        rows.append(
            {
                "id": "resume-add",
                "title": "The last add was stopped",
                "detail": "Resume it, or check the folder for new files.",
                "actions": [{"id": "resume", "label": "Resume"}],
                "counts": True,
            }
        )
    elif last_failed:
        retry = (
            {"id": "rescan", "label": "Try again"}
            if has_folder
            else {"id": "add-folder", "label": "Add a folder"}
        )
        rows.append(
            {
                "id": "failed-add",
                "title": "The last add failed",
                "detail": "Try that folder again. Photos already added stay in the library.",
                "actions": [retry],
                "counts": True,
            }
        )
    if not job_active and index_state == "unindexed":
        follow = (
            {"id": "rescan", "label": "Check for new files"}
            if has_folder
            else {"id": "add-folder", "label": "Add a folder"}
        )
        rows.append(
            {
                "id": "unindexed",
                "title": "Semblon has not looked at this photo",
                "detail": index_note or "Add its folder so search can see inside it.",
                "actions": [follow],
                "counts": True,
            }
        )

    count = sum(1 for row in rows if row.get("counts"))
    if count == 0:
        if library_count <= 0:
            detail = "No folder is added yet. Nothing is scanning."
            actions = [{"id": "add-folder", "label": "Add a folder"}]
            title = "Nothing is scanning"
        else:
            base = library_summary or f"{library_count} photos. Originals stay where they are."
            detail = f"Nothing is scanning. {base}"
            actions = (
                [{"id": "rescan", "label": "Check for new files"}]
                if has_folder
                else [{"id": "add-folder", "label": "Add a folder"}]
            )
            title = "Library is quiet"
        rows.append(
            {
                "id": "quiet",
                "title": title,
                "detail": detail,
                "actions": actions,
                "counts": False,
            }
        )
        label = "Quiet"
        summary = detail
    else:
        label = "1 task" if count == 1 else f"{count} tasks"
        summary = "The library stays open while this finishes."

    return {
        "label": label,
        "count": count,
        "quiet": count == 0,
        "summary": summary,
        "rows": rows,
    }
