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
    return f"{done_i} of {total_i}"


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
    kind = (item.get("kind") or "object").replace("_", " ")
    if kind == "face":
        return "Face"
    # Provider strings like open-vocabulary contour stay out of normal copy.
    if kind in {"object", "color", "ocr", "clip", "pose"}:
        return kind.capitalize()
    return "Something in the photo"


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
