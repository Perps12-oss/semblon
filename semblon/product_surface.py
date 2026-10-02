"""User-facing product surface — presentation boundary above the engine.

INTERNAL ENGINEERING MODEL stays in canvas/load_canvas/inspector_verbs/store.
This module translates outcomes for normal users. Advanced/debug strings are
available only when advanced=True. Never writes the store. Never invents
identity. Similarity is not identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# Soft verb labels (UI only — apply_* semantics unchanged).
VERB_LABEL_MERGE = "Combine face groups"
VERB_LABEL_ASSIGN = "Add to person"
VERB_LABEL_SPLIT = "Split faces"
VERB_LABEL_NAME = "Name this person"
VERB_LABEL_RULE_OUT = "Not this person"
VERB_LABEL_IGNORE = "Ignore"

INSPECTOR_HELP = "Select a face in the photo to see what Semblon found."
INSPECTOR_CAPTION = "What you can do"
SEL_HEADING_IDLE = "Nothing selected"
DETAILS_HEADING = "About this"

# Settings — product vs Advanced vs Diagnostics (presentation only).
SETTINGS_TITLE = "Settings"
SETTINGS_LIBRARY = "Library & Storage"
SETTINGS_LIBRARY_HINT = "Folders Semblon watches and where your library lives on this computer."
SETTINGS_PROCESSING = "Local Capabilities"
SETTINGS_PROCESSING_CPU = "What Semblon can do on this computer — honestly reported."
SETTINGS_GPU = "Use GPU when available"
SETTINGS_APPEARANCE = "Appearance & Privacy"
SETTINGS_ABOUT = "About"
SETTINGS_ABOUT_BODY = (
    "Your local, private visual memory. Explore what is in your images "
    "on this PC. Nothing is uploaded."
)
SETTINGS_ADVANCED = "Advanced"
SETTINGS_ADVANCED_HINT = "Keyboard shortcuts and export tools."
SETTINGS_DIAGNOSTICS = "Diagnostics"
SETTINGS_DIAGNOSTICS_HINT = (
    "Technical details for support — runtime, models, schema, and recent jobs. "
    "Not needed for everyday use."
)
SETTINGS_EXPORT_REVIEW = "Open export review page…"
SETTINGS_OPEN_DIAGNOSTICS = "Advanced diagnostics…"
SETTINGS_SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Search", "Ctrl+F"),
    ("Go to", "Ctrl+K"),
    ("Library", "Ctrl+1"),
    ("People", "Ctrl+2"),
    ("Activity", "Ctrl+3"),
)

# People / Unknown — short workflow coaching (never lectures; identity-safe).
PEOPLE_LIST_HEAD = "People you have named"
PEOPLE_LIST_HINT = (
    "Select a person, then choose faces under People to name to add them."
)
UNKNOWN_COACH = (
    "Browse the groups. Name someone when you recognise them — "
    "or leave them unknown."
)
UNKNOWN_SAFETY = "Unknown is fine. A group is not a person until you name them."


def basename_path(path: str | None) -> str:
    if not path:
        return "Photo"
    return Path(str(path).replace("\\", "/")).name or "Photo"


def soft_media_list_label(
    media: dict,
    *,
    face_count: int = 0,
    item_count: int | None = None,
) -> str:
    """Library row for normals — filename + face count, no path/UUID/state=."""
    name = basename_path(media.get("path"))
    n = int(face_count or 0)
    if n <= 0:
        bit = "no faces"
    elif n == 1:
        bit = "1 face"
    else:
        bit = f"{n} faces"
    return f"{name}  ·  {bit}"


def soft_canvas_status(
    *,
    photo_count: int,
    face_count: int,
    named_people: int = 0,
    unknown_faces: int = 0,
) -> str:
    """Photos workspace purpose line — counts, not telemetry."""
    photos = int(photo_count or 0)
    faces = int(face_count or 0)
    named = int(named_people or 0)
    unknown = int(unknown_faces or 0)
    p = "photo" if photos == 1 else "photos"
    bits = [f"{photos} {p}"]
    if named:
        bits.append(f"{named} people")
    if unknown:
        u = "unknown" if unknown == 1 else "unknown"
        bits.append(f"{unknown} {u}")
    elif faces:
        f = "face" if faces == 1 else "faces"
        bits.append(f"{faces} {f}")
    return "  ·  ".join(bits)


def soft_sel_item_label(it: dict) -> str:
    """Inspector selection row — never a bare UUID."""
    kind = it.get("kind")
    if kind == "cluster":
        names = [n for n in (it.get("person_names") or []) if n]
        n = it.get("face_count")
        if names:
            return f"Face group · {names[0]}"
        if n:
            return f"Face group · {n} face{'s' if int(n) != 1 else ''}"
        return "Face group"
    name = (it.get("display_name") or it.get("person_name") or "").strip()
    if name:
        return name
    if it.get("person_id"):
        return "Named person"
    return "Unknown person"


def soft_progress_clock(*, files_processed: int | None, files_total: int | None) -> str:
    """Product progress fragment — never raw wall-clock / elapsed telemetry."""
    return soft_progress_counts(files_processed=files_processed, files_total=files_total)


def soft_progress_counts(
    *,
    files_processed: int | None,
    files_total: int | None,
    unit: str = "photos",
) -> str:
    """Human \"N of M photos\" — never Current:/elapsed/eta machine dump."""
    done = files_processed
    total = files_total
    if done is None or total is None:
        return ""
    try:
        done_i, total_i = int(done), int(total)
    except (TypeError, ValueError):
        return ""
    if total_i <= 0:
        return ""
    noun = unit if total_i != 1 else unit.rstrip("s")
    return f"{done_i:,} of {total_i:,} {noun}"


# Early ETA stays soft until enough real work has landed.
_ETA_MIN_PROCESSED = 40
_ETA_MIN_ELAPSED_S = 45.0
_ETA_MIN_FRACTION = 0.02


def format_soft_remaining(seconds: float | None) -> str | None:
    """About-N wording for remaining time. Never H:MM:SS wall-clock."""
    if seconds is None:
        return None
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return None
    if s <= 0 or s != s:  # NaN
        return None
    if s < 90:
        return "About a minute left"
    if s < 3600:
        minutes = max(2, int(round(s / 60.0)))
        return f"About {minutes} minutes left"
    hours = s / 3600.0
    if hours < 1.5:
        return "About an hour left"
    if hours < 48:
        return f"About {int(round(hours))} hours left"
    days = max(2, int(round(hours / 24.0)))
    return f"About {days} days left"


def eta_is_trustworthy(
    *,
    files_processed: int | None,
    files_total: int | None,
    elapsed_s: float | None,
    eta_s: float | None,
) -> bool:
    """True only when a remaining-time guess is grounded in enough work."""
    if eta_s is None or files_processed is None or files_total is None:
        return False
    try:
        done = int(files_processed)
        total = int(files_total)
        elapsed = float(elapsed_s) if elapsed_s is not None else 0.0
        eta = float(eta_s)
    except (TypeError, ValueError):
        return False
    if done <= 0 or total <= done or eta <= 0 or elapsed < _ETA_MIN_ELAPSED_S:
        return False
    if done < _ETA_MIN_PROCESSED and (done / total) < _ETA_MIN_FRACTION:
        return False
    return True


def soft_eta_line(
    *,
    files_processed: int | None = None,
    files_total: int | None = None,
    elapsed_s: float | None = None,
    eta_s: float | None = None,
    paused: bool = False,
) -> str:
    """Product ETA. Early jobs say Estimating… — never raw eta/elapsed clocks."""
    if paused:
        return "Paused — resume when you are ready"
    if not eta_is_trustworthy(
        files_processed=files_processed,
        files_total=files_total,
        elapsed_s=elapsed_s,
        eta_s=eta_s,
    ):
        return "Estimating time remaining…"
    human = format_soft_remaining(eta_s)
    return human or "Estimating time remaining…"


def soft_faces_found_line(faces_found: int | None) -> str:
    """Faces are observations — never imply face count = people."""
    if faces_found is None:
        return ""
    try:
        n = int(faces_found)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        return ""
    if n == 0:
        return "No faces found yet"
    if n == 1:
        return "1 face found"
    return f"{n:,} faces found"


def processing_home_headline(
    *,
    paused: bool = False,
    stage: str | None = None,
    kind: str | None = None,
) -> str:
    """Scan card title. Deck labels; failed and cancelled stay explicit."""
    from semblon.scan_present import scan_title

    return scan_title(stage=stage, kind=kind, paused=paused)


def processing_home_activity(*, paused: bool = False) -> str:
    if paused:
        return "Paused between photos. Resume to continue, or cancel to stop."
    return "Finding faces and preparing your library. Pause or cancel anytime."


def product_status_text(
    ev: Any,
    *,
    paused: bool = False,
) -> str:
    """Home / product chrome status. No Current: filename, no elapsed/eta dump."""
    stage = getattr(ev, "stage", None)
    kind = getattr(ev, "kind", None)
    if paused:
        return "Paused"
    if kind == "stalled":
        return "Still working — this is taking longer than usual"
    if kind == "cancelled":
        return "Cancelled"
    if kind == "failed":
        return "Couldn't finish"
    if kind == "completed":
        return "Completed"
    headline = processing_home_headline(paused=False, stage=stage, kind=kind)
    counts = soft_progress_counts(
        files_processed=getattr(ev, "files_processed", None),
        files_total=getattr(ev, "files_total", None),
    )
    faces = soft_faces_found_line(getattr(ev, "faces_found", None))
    bits = [headline if headline.endswith("…") else f"{headline}…"]
    if counts:
        bits.append(counts)
    if faces:
        bits.append(faces)
    return "  ·  ".join(bits)


def processing_home_snapshot(
    ev: Any | None = None,
    *,
    paused: bool = False,
    files_processed: int | None = None,
    files_total: int | None = None,
    faces_found: int | None = None,
    elapsed_s: float | None = None,
    eta_s: float | None = None,
    stage: str | None = None,
    kind: str | None = None,
    pace: Any | None = None,
) -> dict[str, str]:
    """Structured copy for the processing Home workspace.

    ``eta`` is the scan meta line (percent, elapsed, ETA) from real counters.
    ``eta_s`` on the event is not shown as a made-up sentence. Pace, when
    passed, is the file-rate EMA owned by the Home session.
    """
    from semblon.scan_present import ScanPace, scan_card

    if ev is not None:
        files_processed = getattr(ev, "files_processed", files_processed)
        files_total = getattr(ev, "files_total", files_total)
        faces_found = getattr(ev, "faces_found", faces_found)
        elapsed_s = getattr(ev, "elapsed_s", elapsed_s)
        eta_s = getattr(ev, "eta_s", eta_s)
        stage = getattr(ev, "stage", stage)
        kind = getattr(ev, "kind", kind)
    if pace is None and not paused and elapsed_s is not None and files_processed:
        pace = ScanPace()
        pace.observe(files_processed, elapsed_s)
    card = scan_card(
        stage=stage,
        kind=kind,
        paused=paused,
        files_processed=files_processed,
        files_total=files_total,
        faces_found=faces_found,
        elapsed_s=elapsed_s,
        pace=pace,
    )
    _ = eta_s  # event field stays available; the card computes ETA from pace
    return {
        "headline": card["title"],
        "activity": processing_home_activity(paused=paused),
        "progress": card["stats"],
        "faces": soft_faces_found_line(faces_found),
        "eta": card["meta"],
        "folder_note": (
            "Getting your library ready. You can add another folder when this finishes."
            if not paused
            else "Paused. Resume to continue, or cancel to stop this scan."
        ),
    }


def soft_person_label(face: dict | None, *, board: dict | None = None) -> str:
    """Named person or Unknown — never a bare person_id UUID."""
    if not face:
        return "Unknown person"
    pid = face.get("person_id")
    if pid and board:
        for p in board.get("persons") or []:
            if p.get("person_id") == pid:
                name = (p.get("display_name") or "").strip()
                if name:
                    return name
    # decisions / display may already be stamped on face in some boards
    for key in ("display_name", "person_name", "name"):
        name = (face.get(key) or "").strip()
        if name:
            return name
    if pid:
        return "Named person"
    return "Unknown person"


def soft_object_label(item: dict) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else None
    if payload is None and isinstance(item.get("payload_json"), str):
        try:
            import json

            payload = json.loads(item.get("payload_json") or "{}")
        except Exception:
            payload = None
    if not isinstance(payload, dict):
        payload = {}
    if item.get("provider") == "visual.region" or payload.get("class") == "visual_region":
        label = payload.get("selected_label")
        return label if label else ""
    label = payload.get("label") or payload.get("visual_label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    kind = (item.get("kind") or "object").replace("_", " ")
    if kind == "face":
        return "Face"
    # Provider strings like open-vocabulary contour stay out of normal copy.
    if kind in {"object", "color", "ocr", "clip", "pose"}:
        return kind.capitalize()
    return "Something in the photo"


def soft_inspector_for_visual_segment(seg: dict) -> list[str]:
    """Inspector copy for an open-vocabulary VisualSegment. Never invents a person name."""
    label = (seg.get("label") or "region").strip() or "region"
    conf = seg.get("confidence")
    provider = seg.get("source_provider") or seg.get("provider") or ""
    titled = label[0].upper() + label[1:] if label else "Region"
    lines = [titled, ""]
    lines.append("Semblon recognised a visual region here. This is not a person identity.")
    if isinstance(conf, (int, float)) and conf > 0:
        lines.append(f"Confidence {conf:.0%}")
    if provider and provider not in {"local_opencv", "semantic_visual"}:
        lines.append(f"Source: {provider}")
    lines.append("Press Esc or click empty space to clear the selection.")
    return lines


def soft_inspector_for_media(board: dict, media_id: str | None) -> list[str]:
    """Normal Inspector when a photo is shown but nothing is selected."""
    if not media_id:
        return [
            "Photos",
            "Open a photo to explore what Semblon found.",
            "Tip: move the pointer over the photo, or drag a box to look closely.",
        ]
    media = next(
        (m for m in (board.get("media") or []) if m.get("media_id") == media_id),
        None,
    )
    faces = [f for f in (board.get("faces") or []) if f.get("media_id") == media_id]
    named = sum(1 for f in faces if f.get("person_id"))
    unknown = sum(1 for f in faces if not f.get("person_id"))
    objects = [
        i
        for i in (board.get("items") or [])
        if i.get("media_id") == media_id and i.get("kind") != "face" and i.get("bbox_x1") is not None
    ]
    lines = [
        basename_path(media.get("path") if media else None),
        "",
    ]
    if faces:
        lines.append(f"{len(faces)} face{'s' if len(faces) != 1 else ''} found")
        if named:
            lines.append(f"{named} named")
        if unknown:
            lines.append(f"{unknown} unknown")
    else:
        lines.append("No faces found in this photo")
    if objects:
        lines.append(
            f"{len(objects)} other detail{'s' if len(objects) != 1 else ''} available"
        )
    lines.append("")
    lines.append("Move over the photo to discover faces. Click one to select it.")
    lines.append("Or drag a box over any area to look more closely.")
    lines.append("Open Lens to ask about a region with available understanding.")
    return lines


def soft_inspector_for_face(face: dict, board: dict) -> list[str]:
    """Human outcome for a selected face — memory + uncertainty, not UUIDs."""
    label = soft_person_label(face, board=board)
    lines = [label, ""]
    pid = face.get("person_id")
    if pid:
        same = [
            f
            for f in (board.get("faces") or [])
            if f.get("person_id") == pid
        ]
        media_ids = {f.get("media_id") for f in same if f.get("media_id")}
        lines.append("Possible match — not confirmed")
        if len(media_ids) > 1:
            lines.append(f"Seen in {len(media_ids)} photos")
        elif len(same) > 1:
            lines.append(f"Seen {len(same)} times")
        lines.append("Similarity is not identity — you decide the name.")
    else:
        lines.append("Not confirmed")
        lines.append("Semblon found a face but has not connected it to a named person.")
        lines.append("Name them when you are sure.")
    lines.append("")
    lines.append("Press Esc or click empty space to clear the selection.")
    return lines


def soft_inspector_for_item(item: dict) -> list[str]:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    if item.get("provider") == "visual.region" or payload.get("class") == "visual_region":
        label = (payload.get("selected_label") or "").strip()
        lines = [label if label else "This part of the photo", ""]
        parent = (payload.get("parent_label") or "").strip()
        if parent:
            lines.append(f"Part of: {parent}")
        related = [
            text
            for text in (payload.get("related_labels") or [])
            if text and text != label
        ]
        if related:
            lines.append("Related: " + ", ".join(related[:4]))
        if payload.get("proper_name_proposals"):
            lines.append("A name was suggested. It is not a person identity.")
        lines.append("This is not a person identity.")
        lines.append("Press Esc or click empty space to clear the selection.")
        return lines
    if payload.get("visual_segment") or payload.get("label"):
        return soft_inspector_for_visual_segment(
            {
                "label": payload.get("label") or soft_object_label(item),
                "confidence": item.get("score") or payload.get("confidence"),
                "source_provider": item.get("provider"),
            }
        )
    return [
        soft_object_label(item),
        "",
        "Semblon noticed something here. This is not a person identity.",
        "Press Esc or click empty space to clear the selection.",
    ]


def soft_inspector_for_region(
    hits: list[dict],
    *,
    empty: bool = False,
) -> list[str]:
    """Drag-to-look result. Distinguishes face / person / unknown / object / nothing."""
    if empty or not hits:
        return [
            "Nothing found here",
            "",
            "Semblon did not find a face or other detail in that area.",
            "Try another region, or move over a face you can already see.",
        ]
    faces = [h for h in hits if h.get("kind") == "face"]
    objects = [h for h in hits if h.get("kind") != "face"]
    lines = ["Looking here", ""]
    if faces:
        named = [h for h in faces if h.get("person_label") and h.get("person_label") != "Unknown person"]
        unknown = [h for h in faces if not h.get("person_label") or h.get("person_label") == "Unknown person"]
        lines.append(f"{len(faces)} face{'s' if len(faces) != 1 else ''}")
        for h in named[:5]:
            lines.append(f"  · {h['person_label']} (recognised)")
        for h in unknown[:5]:
            lines.append("  · Unknown person")
        lines.append("Recognition is not automatic identity — you decide the name.")
    if objects:
        lines.append(
            f"{len(objects)} other detail{'s' if len(objects) != 1 else ''}"
        )
        for h in objects[:5]:
            lines.append(f"  · {h.get('label') or 'Something in the photo'}")
    lines.append("")
    lines.append("Click a face to select it, or Esc to clear.")
    return lines


def advanced_inspector_for_media(board: dict, media_id: str | None) -> list[str]:
    """Engineering dump — progressive disclosure only."""
    from semblon.canvas import media_inspector_lines

    return media_inspector_lines(board, media_id)


def region_hits(
    board: dict,
    media_id: str,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> list[dict]:
    """Hit-test stored observation boxes against an image-space rectangle.

    Coordinates are original image pixels (same space as face bboxes).
    """
    rx1, rx2 = sorted((float(x1), float(x2)))
    ry1, ry2 = sorted((float(y1), float(y2)))
    if rx2 - rx1 < 1 or ry2 - ry1 < 1:
        return []

    def _overlap(bx1, by1, bx2, by2) -> bool:
        if None in (bx1, by1, bx2, by2):
            return False
        return not (bx2 < rx1 or bx1 > rx2 or by2 < ry1 or by1 > ry2)

    hits: list[dict] = []
    for f in board.get("faces") or []:
        if f.get("media_id") != media_id:
            continue
        if _overlap(f.get("bbox_x1"), f.get("bbox_y1"), f.get("bbox_x2"), f.get("bbox_y2")):
            hits.append(
                {
                    "kind": "face",
                    "id": f.get("face_id"),
                    "face": f,
                    "person_label": soft_person_label(f, board=board),
                    "bbox": [
                        f.get("bbox_x1"),
                        f.get("bbox_y1"),
                        f.get("bbox_x2"),
                        f.get("bbox_y2"),
                    ],
                }
            )
    for it in board.get("items") or []:
        if it.get("media_id") != media_id or it.get("kind") == "face":
            continue
        if _overlap(it.get("bbox_x1"), it.get("bbox_y1"), it.get("bbox_x2"), it.get("bbox_y2")):
            hits.append(
                {
                    "kind": it.get("kind") or "object",
                    "id": it.get("item_id"),
                    "item": it,
                    "label": soft_object_label(it),
                    "bbox": [
                        it.get("bbox_x1"),
                        it.get("bbox_y1"),
                        it.get("bbox_x2"),
                        it.get("bbox_y2"),
                    ],
                }
            )
    return hits


def display_rect_for_bbox(
    bbox: list | tuple,
    *,
    scale: float,
) -> tuple[float, float, float, float] | None:
    if not bbox or len(bbox) < 4 or None in bbox[:4]:
        return None
    x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return (x1 * scale, y1 * scale, x2 * scale, y2 * scale)


class SettingsSection:
    """One Settings body Home already draws. Not a second window or catalogue."""

    def __init__(self, id: str, title: str, hint: str = ""):
        self.id = id
        self.title = title
        self.hint = hint


def settings_contributions() -> tuple[SettingsSection, ...]:
    """Product sections. Home still builds the window."""
    return (
        SettingsSection("library", SETTINGS_LIBRARY, SETTINGS_LIBRARY_HINT),
        SettingsSection("processing", SETTINGS_PROCESSING, SETTINGS_PROCESSING_CPU),
        SettingsSection("appearance", SETTINGS_APPEARANCE),
        SettingsSection("about", SETTINGS_ABOUT, SETTINGS_ABOUT_BODY),
    )


def settings_product_section_titles() -> tuple[str, ...]:
    """Everyday Settings sections a non-technical user understands."""
    return tuple(section.title for section in settings_contributions())


def settings_forbidden_product_vocab() -> tuple[str, ...]:
    """Strings that must stay in Diagnostics — never everyday Settings copy."""
    return (
        "buffalo_l",
        "FaceKit",
        "pack_id",
        "schema_version",
        "onnx",
        "JobEngine",
        "execution_provider",
        "modality=",
        "embeddings.modality",
        "faces.person_id",
        "ANN",
        "DBSCAN",
        "InsightFace",
    )


def soft_people_header_lines() -> list[str]:
    """People list header — workflow, not architecture lecture."""
    return [PEOPLE_LIST_HEAD, PEOPLE_LIST_HINT]


def soft_unknown_coach_lines(*, waiting: int) -> list[str]:
    """People to name coaching. Unknown valid; cluster ≠ person; no auto-assign."""
    from semblon.library_status import people_to_name_text

    n = int(waiting or 0)
    if n <= 0:
        head = "No people to name."
    else:
        head = people_to_name_text(n) + "."
    return [head, UNKNOWN_COACH, UNKNOWN_SAFETY]
