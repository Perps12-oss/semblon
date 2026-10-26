"""Resumable still tiers. The days-long DINOv2 tail is not on the critical path.

Tier 0 (library): hash, orientation, embedded thumbnail, media row.
Tier 1 (observe): faces, histogram, contours, and the other non-region observers.
Tier 2 (semantic): DINOv2 region tokens, and only those.

``work_items.tier_done_mask`` is the skip-if-done record. A restart reads it
and does not pay for a tier whose bit is already set. Model code is not
involved; this module only decides what runs next.
"""

from __future__ import annotations

import struct
from pathlib import Path

TIER_LIBRARY = 1
TIER_OBSERVE = 2
TIER_SEMANTIC = 4
TIER_DETAIL = 8

# Face detection always runs in tier 1, whether or not it is listed.
_OBSERVE_TOKENS = frozenset({"color", "appearance", "object", "text", "ocr", "pose", "clip"})
# ``region`` is the whole job. ``region-lite`` stops after the whole-picture pass.
_SEMANTIC_TOKENS = frozenset({"region", "region-lite"})
_SEMANTIC_MODALITIES = ("region", "scene", "patch")

WORK_ITEMS_DDL = """
CREATE TABLE IF NOT EXISTS work_items (
  path           TEXT PRIMARY KEY,
  mtime_ns       INTEGER NOT NULL,
  byte_size      INTEGER NOT NULL,
  sha256         TEXT,
  media_id       TEXT,
  tier_done_mask INTEGER NOT NULL DEFAULT 0,
  orientation    INTEGER,
  thumb_jpeg     BLOB,
  updated_at     TEXT
);
"""


def requested_mask(observers: tuple[str, ...]) -> int:
    """Bits this scan is allowed to mark done. Region stays open until asked for."""
    mask = TIER_LIBRARY | TIER_OBSERVE
    if any(token in _SEMANTIC_TOKENS for token in observers):
        mask |= TIER_SEMANTIC
    if "region" in observers:
        mask |= TIER_DETAIL
    return mask


def split_observers(observers: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Non-face observers for tier 1, then the region observer for tier 2."""
    observe = tuple(token for token in observers if token in _OBSERVE_TOKENS)
    semantic = tuple(token for token in observers if token in _SEMANTIC_TOKENS)
    return observe, semantic


def semantic_coverage(conn) -> dict | None:
    """How much of the library the region search can see. None when unknown.

    ``searchable`` photos have the whole-picture pass. ``detailed`` photos also
    have the fine windows and crops. A search over a partly prepared library
    uses this to say so instead of looking complete.
    """
    try:
        row = conn.execute(
            """SELECT COUNT(*),
                      COALESCE(SUM((tier_done_mask & ?) != 0), 0),
                      COALESCE(SUM((tier_done_mask & ?) != 0), 0)
               FROM work_items WHERE media_id IS NOT NULL""",
            (TIER_SEMANTIC, TIER_DETAIL),
        ).fetchone()
    except Exception:  # noqa: BLE001 — older stores have no work_items
        return None
    total = int(row[0] or 0)
    if total <= 0:
        return None
    searchable = int(row[1] or 0)
    detailed = int(row[2] or 0)
    return {
        "total": total,
        "searchable": searchable,
        "detailed": detailed,
        "complete": searchable >= total and detailed >= total,
    }


def coverage_note(coverage: dict | None) -> str:
    """One plain sentence, or empty when nothing is missing."""
    if not coverage or coverage.get("complete"):
        return ""
    total = int(coverage["total"])
    missing = total - int(coverage["searchable"])
    if missing > 0:
        return (
            f"{missing:,} of {total:,} photos are still being prepared for search, "
            "so more matches may appear soon."
        )
    sharper = total - int(coverage["detailed"])
    return (
        f"Fine-detail search is still being added to {sharper:,} of {total:,} photos, "
        "so small details in those may not show up yet."
    )


def ensure_work_items(conn) -> None:
    conn.executescript(WORK_ITEMS_DDL)


def header_geometry(data: bytes) -> tuple[int | None, int | None, int | None, bytes | None]:
    """Width, height, EXIF orientation, and an embedded JPEG thumbnail.

    Dimensions come from the container header. Orientation swaps the pair
    when the tag says the display is rotated. No pixel decode.
    """
    width, height = _header_wh(data)
    orientation, thumb = _jpeg_exif(data) if data[:2] == b"\xff\xd8" else (None, None)
    if width and height and orientation in (5, 6, 7, 8):
        width, height = height, width
    return width, height, orientation, thumb


def load_still(conn, path: Path) -> dict:
    """One queue row. Same mtime and size skips the hash. A change clears the mask."""
    st = path.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    byte_size = int(st.st_size)
    key = str(path)
    row = conn.execute(
        """SELECT sha256, media_id, tier_done_mask, mtime_ns, byte_size
           FROM work_items WHERE path=?""",
        (key,),
    ).fetchone()
    if row is not None and int(row["mtime_ns"]) == mtime_ns and int(row["byte_size"]) == byte_size:
        return {
            "path": path,
            "mtime_ns": mtime_ns,
            "byte_size": byte_size,
            "sha256": row["sha256"],
            "media_id": row["media_id"],
            "mask": int(row["tier_done_mask"] or 0),
            "needs_hash": not row["sha256"],
        }
    found = conn.execute(
        """SELECT media_id, sha256 FROM media
           WHERE path=? AND mtime_ns=? AND byte_size=?""",
        (key, mtime_ns, byte_size),
    ).fetchone()
    if found is not None:
        media_id = str(found["media_id"])
        return {
            "path": path,
            "mtime_ns": mtime_ns,
            "byte_size": byte_size,
            "sha256": found["sha256"],
            "media_id": media_id,
            "mask": infer_mask(conn, media_id),
            "needs_hash": False,
        }
    return {
        "path": path,
        "mtime_ns": mtime_ns,
        "byte_size": byte_size,
        "sha256": None,
        "media_id": None,
        "mask": 0,
        "needs_hash": True,
    }


def infer_mask(conn, media_id: str) -> int:
    """What an older scan already finished, before work_items existed."""
    mask = TIER_LIBRARY
    face = conn.execute(
        """SELECT 1 FROM faces f
           JOIN observations o ON o.observation_id=f.observation_id
           WHERE o.media_id=? LIMIT 1""",
        (media_id,),
    ).fetchone()
    if face is None:
        face = conn.execute(
            """SELECT 1 FROM observation_items i
               JOIN observations o ON o.observation_id=i.observation_id
               WHERE o.media_id=? AND i.kind IN ('face','appearance','object')
               LIMIT 1""",
            (media_id,),
        ).fetchone()
    if face is not None:
        mask |= TIER_OBSERVE
    semantic = conn.execute(
        f"""SELECT 1 FROM embeddings e
            JOIN observation_items i ON i.item_id=e.item_id
            JOIN observations o ON o.observation_id=i.observation_id
            WHERE o.media_id=? AND e.modality IN ({",".join("?" * len(_SEMANTIC_MODALITIES))})
            LIMIT 1""",
        (media_id, *_SEMANTIC_MODALITIES),
    ).fetchone()
    if semantic is not None:
        mask |= TIER_SEMANTIC
        detail = conn.execute(
            """SELECT 1 FROM observation_items i
               JOIN observations o ON o.observation_id=i.observation_id
               WHERE o.media_id=? AND i.kind='clip'
                 AND (i.payload_json LIKE '%"role": "region"%'
                      OR i.payload_json LIKE '%"window"%')
               LIMIT 1""",
            (media_id,),
        ).fetchone()
        if detail is not None:
            mask |= TIER_DETAIL
        else:
            # Pictures too small for windows or proposals have no detail to add.
            size = conn.execute(
                "SELECT width, height FROM media WHERE media_id=?", (media_id,)
            ).fetchone()
            if size is not None and min(int(size[0] or 0), int(size[1] or 0)) < 64:
                mask |= TIER_DETAIL
    return mask


def save_work_item(
    conn,
    *,
    path: Path,
    mtime_ns: int,
    byte_size: int,
    sha256: str | None,
    media_id: str | None,
    mask: int,
    orientation: int | None = None,
    thumb_jpeg: bytes | None = None,
    updated_at: str,
) -> None:
    conn.execute(
        """INSERT INTO work_items(
             path, mtime_ns, byte_size, sha256, media_id, tier_done_mask,
             orientation, thumb_jpeg, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             mtime_ns=excluded.mtime_ns,
             byte_size=excluded.byte_size,
             sha256=excluded.sha256,
             media_id=excluded.media_id,
             tier_done_mask=excluded.tier_done_mask,
             orientation=COALESCE(excluded.orientation, work_items.orientation),
             thumb_jpeg=COALESCE(excluded.thumb_jpeg, work_items.thumb_jpeg),
             updated_at=excluded.updated_at
        """,
        (
            str(path),
            int(mtime_ns),
            int(byte_size),
            sha256,
            media_id,
            int(mask),
            orientation,
            thumb_jpeg,
            updated_at,
        ),
    )


def still_observation_id(conn, media_id: str, run_id: str) -> str | None:
    row = conn.execute(
        """SELECT observation_id FROM observations
           WHERE media_id=? AND run_id=? AND frame_id IS NULL""",
        (media_id, run_id),
    ).fetchone()
    if row is None:
        return None
    return str(row["observation_id"])


def _header_wh(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if len(data) >= 26 and data[:2] == b"BM":
        width, height = struct.unpack("<ii", data[18:26])
        return abs(int(width)), abs(int(height))
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        return None, None
    if data[:2] == b"\xff\xd8":
        return _jpeg_sof_wh(data)
    return None, None


def _jpeg_sof_wh(data: bytes) -> tuple[int | None, int | None]:
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    standalone = {0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8}
    i = 2
    n = len(data)
    while i < n:
        if data[i] != 0xFF:
            return None, None
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return None, None
        marker = data[i]
        i += 1
        if marker in (0xD9, 0xDA):
            return None, None
        if marker in standalone or marker == 0x00:
            continue
        if i + 1 >= n:
            return None, None
        seglen = int.from_bytes(data[i : i + 2], "big")
        if seglen < 2 or i + seglen > n:
            return None, None
        if marker in sof and seglen >= 7 and i + 7 <= n:
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            if width and height:
                return int(width), int(height)
            return None, None
        i += seglen
    return None, None


def _jpeg_exif(data: bytes) -> tuple[int | None, bytes | None]:
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            return None, None
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return None, None
        marker = data[i]
        i += 1
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0xD9, 0xDA):
            return None, None
        if i + 2 > n:
            return None, None
        seglen = int.from_bytes(data[i : i + 2], "big")
        if seglen < 2 or i + seglen > n:
            return None, None
        if marker == 0xE1:
            payload = data[i + 2 : i + seglen]
            if payload.startswith(b"Exif\x00\x00"):
                return _tiff_orientation_thumb(payload[6:])
        i += seglen
    return None, None


def _tiff_orientation_thumb(tiff: bytes) -> tuple[int | None, bytes | None]:
    if len(tiff) < 8:
        return None, None
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return None, None
    if struct.unpack(endian + "H", tiff[2:4])[0] != 42:
        return None, None
    offset = struct.unpack(endian + "I", tiff[4:8])[0]
    orientation = None
    thumb = None
    for _ in range(4):
        if offset <= 0 or offset + 2 > len(tiff):
            break
        count = struct.unpack(endian + "H", tiff[offset : offset + 2])[0]
        pos = offset + 2
        jpeg_off = None
        jpeg_len = None
        for _entry in range(count):
            if pos + 12 > len(tiff):
                break
            tag, _typ, _count = struct.unpack(endian + "HHI", tiff[pos : pos + 8])
            value = tiff[pos + 8 : pos + 12]
            if tag == 0x0112 and len(value) >= 2:
                orientation = int(struct.unpack(endian + "H", value[:2])[0])
            elif tag == 0x0201 and len(value) == 4:
                jpeg_off = int(struct.unpack(endian + "I", value)[0])
            elif tag == 0x0202 and len(value) == 4:
                jpeg_len = int(struct.unpack(endian + "I", value)[0])
            pos += 12
        if (
            jpeg_off
            and jpeg_len
            and jpeg_off >= 0
            and jpeg_off + jpeg_len <= len(tiff)
        ):
            blob = bytes(tiff[jpeg_off : jpeg_off + jpeg_len])
            if blob.startswith(b"\xff\xd8"):
                thumb = blob
        if pos + 4 > len(tiff):
            break
        offset = int(struct.unpack(endian + "I", tiff[pos : pos + 4])[0])
    return orientation, thumb
