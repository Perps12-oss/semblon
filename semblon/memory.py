"""S6 visual memory: when / where / with whom. Read-only. Not identity.

Does not invent schema columns. Time comes from EXIF, filename, or mtime_ns.
Place is folder path plus GPS if EXIF has it. No geocoding. No CLIP.
Time and place must not change compare() or cluster membership.
"""

from __future__ import annotations

import re
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

BURST_NS = 90 * 1_000_000_000
_FN_TIME = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})")


class MemoryError(ValueError):
    pass


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise MemoryError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _require_person(conn, person: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM persons WHERE person_id=?", (person,)
    ).fetchone()
    if row is None:
        row = conn.execute(
            """SELECT * FROM persons
               WHERE status='active' AND display_name=?
               ORDER BY person_id LIMIT 1""",
            (person,),
        ).fetchone()
    if row is None:
        raise MemoryError(f"unknown person: {person}")
    return row


def _dt_to_ns(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def _filename_when_ns(path: str) -> int | None:
    m = _FN_TIME.search(Path(path).name)
    if not m:
        return None
    try:
        dt = datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), int(m.group(6)),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
    return _dt_to_ns(dt)


def _parse_exif_datetime(raw: bytes) -> datetime | None:
    try:
        s = raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        dt = datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, UnicodeError):
        return None


def _rational(buf: bytes, count: int, endian: str) -> list[float]:
    out = []
    fmt = endian + "II"
    for i in range(count):
        num, den = struct.unpack_from(fmt, buf, i * 8)
        out.append(num / den if den else 0.0)
    return out


def _dms_to_deg(vals: list[float], ref: bytes) -> float | None:
    if len(vals) < 3:
        return None
    deg = vals[0] + vals[1] / 60.0 + vals[2] / 3600.0
    if ref[:1] in (b"S", b"W"):
        deg = -deg
    return deg


def read_still_exif(path: Path) -> dict:
    """Best-effort JPEG EXIF. Empty dict if missing or not JPEG."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = p.read_bytes()
    except OSError:
        return {}
    if not data.startswith(b"\xff\xd8"):
        return {}
    i = 2
    app1 = None
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:
            break
        seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
        payload = data[i + 4 : i + 2 + seglen]
        i += 2 + seglen
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            app1 = payload[6:]
            break
    if not app1 or len(app1) < 8:
        return {}
    endian = "<" if app1[:2] == b"II" else ">"
    ifd0 = struct.unpack(endian + "I", app1[4:8])[0]
    out: dict = {}
    exif_off = gps_off = None

    def read_ifd(off: int):
        nonlocal exif_off, gps_off
        if off + 2 > len(app1):
            return
        n = struct.unpack_from(endian + "H", app1, off)[0]
        for k in range(n):
            e = off + 2 + k * 12
            if e + 12 > len(app1):
                return
            tag, typ, cnt, val = struct.unpack_from(endian + "HHI4s", app1, e)
            if tag == 0x8769 and typ == 4:
                exif_off = struct.unpack(endian + "I", val)[0]
            elif tag == 0x8825 and typ == 4:
                gps_off = struct.unpack(endian + "I", val)[0]
            elif tag in (0x0132, 0x9003) and typ == 2:
                voff = struct.unpack(endian + "I", val)[0] if cnt > 4 else None
                raw = app1[voff : voff + cnt] if voff else val[:cnt]
                dt = _parse_exif_datetime(raw)
                if dt is not None:
                    key = "datetime_original" if tag == 0x9003 else "datetime"
                    out[key] = dt.isoformat()
                    out[key + "_ns"] = _dt_to_ns(dt)

    read_ifd(ifd0)
    if exif_off:
        read_ifd(exif_off)
    if gps_off and gps_off + 2 <= len(app1):
        n = struct.unpack_from(endian + "H", app1, gps_off)[0]
        lat = lon = lat_ref = lon_ref = None
        for k in range(n):
            e = gps_off + 2 + k * 12
            if e + 12 > len(app1):
                break
            tag, typ, cnt, val = struct.unpack_from(endian + "HHI4s", app1, e)
            if tag == 1 and typ == 2:
                lat_ref = val
            elif tag == 3 and typ == 2:
                lon_ref = val
            elif tag in (2, 4) and typ == 5:
                voff = struct.unpack(endian + "I", val)[0]
                nums = _rational(app1[voff : voff + cnt * 8], cnt, endian)
                if tag == 2:
                    lat = nums
                else:
                    lon = nums
        if lat and lon and lat_ref and lon_ref:
            la = _dms_to_deg(lat, lat_ref)
            lo = _dms_to_deg(lon, lon_ref)
            if la is not None and lo is not None:
                out["lat"] = round(la, 6)
                out["lon"] = round(lo, 6)
    return out


def when_where(path: str, mtime_ns: int | None) -> dict:
    exif = read_still_exif(Path(path)) if path else {}
    ns = exif.get("datetime_original_ns") or exif.get("datetime_ns")
    source = "exif"
    if ns is None:
        ns = _filename_when_ns(path)
        source = "filename"
    if ns is None:
        ns = int(mtime_ns) if mtime_ns else None
        source = "mtime"
    folder = Path(path).parent.name if path else ""
    rec = {
        "when_ns": ns,
        "when": datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat() if ns else None,
        "when_source": source if ns else None,
        "folder": folder or None,
        "path": path,
    }
    if "lat" in exif:
        rec["lat"] = exif["lat"]
        rec["lon"] = exif["lon"]
        rec["place_source"] = "exif_gps"
    else:
        rec["place_source"] = "folder"
    return rec


def _named_rows(conn, run_id: str | None, person_id: str | None):
    sql = """
        SELECT f.face_id, f.person_id, f.status, f.size_band, f.face_w, f.face_h,
               p.display_name, m.media_id, m.path, m.mtime_ns
        FROM faces f
        JOIN persons p ON p.person_id = f.person_id
        JOIN observations o ON o.observation_id = f.observation_id
        JOIN media m ON m.media_id = o.media_id
        WHERE f.status='ok' AND f.person_id IS NOT NULL AND p.status='active'
    """
    args: list = []
    if run_id:
        sql += " AND f.run_id=?"
        args.append(run_id)
    if person_id:
        sql += " AND f.person_id=?"
        args.append(person_id)
    sql += " ORDER BY f.face_id"
    return conn.execute(sql, args).fetchall()


def history(store: Path, *, person: str, run_id: str | None = None) -> dict:
    """Person × time/place. Does not identify. Does not write."""
    conn = _connect_ro(store)
    try:
        prow = _require_person(conn, person)
        rows = _named_rows(conn, run_id, prow["person_id"])
        items = []
        for r in rows:
            ww = when_where(r["path"], r["mtime_ns"])
            items.append({
                "face_id": r["face_id"],
                "media_id": r["media_id"],
                "size_band": r["size_band"],
                **ww,
            })
        items.sort(key=lambda x: (x["when_ns"] is None, x["when_ns"] or 0, x["face_id"]))
        return {
            "person_id": prow["person_id"],
            "display_name": prow["display_name"],
            "sightings": len(items),
            "items": items,
            "note": "S6 memory; not identity. Time/place do not change pack_id compare.",
        }
    finally:
        conn.close()


def together(store: Path, *, run_id: str | None = None) -> dict:
    """Named people on the same still. Cluster is not a person."""
    conn = _connect_ro(store)
    try:
        rows = _named_rows(conn, run_id, None)
        by_media: dict[str, dict] = {}
        for r in rows:
            rec = by_media.setdefault(
                r["media_id"],
                {"media_id": r["media_id"], "path": r["path"], "mtime_ns": r["mtime_ns"], "people": {}},
            )
            rec["people"][r["person_id"]] = r["display_name"]
        pairs = []
        for rec in by_media.values():
            people = rec["people"]
            if len(people) < 2:
                continue
            ww = when_where(rec["path"], rec["mtime_ns"])
            ids = sorted(people)
            pairs.append({
                "media_id": rec["media_id"],
                "person_ids": ids,
                "names": [people[i] for i in ids],
                **ww,
            })
        pairs.sort(key=lambda x: (x["when_ns"] is None, x["when_ns"] or 0, x["media_id"]))
        return {
            "pairs": len(pairs),
            "items": pairs,
            "note": "co-appearance on one still; not a cluster merge",
        }
    finally:
        conn.close()


def events(store: Path, *, run_id: str | None = None) -> dict:
    """Structured events: burst, day, folder. No LLM titles."""
    conn = _connect_ro(store)
    try:
        rows = _named_rows(conn, run_id, None)
        sightings = []
        for r in rows:
            ww = when_where(r["path"], r["mtime_ns"])
            sightings.append({
                "face_id": r["face_id"],
                "person_id": r["person_id"],
                "display_name": r["display_name"],
                "media_id": r["media_id"],
                **ww,
            })
        # Bursts: same folder, adjacent times within BURST_NS, 2+ media.
        dated = [s for s in sightings if s["when_ns"] is not None]
        dated.sort(key=lambda s: (s["folder"] or "", s["when_ns"], s["media_id"]))
        bursts = []
        i = 0
        while i < len(dated):
            j = i + 1
            media = {dated[i]["media_id"]}
            people = {dated[i]["person_id"]}
            while (
                j < len(dated)
                and dated[j]["folder"] == dated[i]["folder"]
                and dated[j]["when_ns"] - dated[j - 1]["when_ns"] <= BURST_NS
            ):
                media.add(dated[j]["media_id"])
                people.add(dated[j]["person_id"])
                j += 1
            if len(media) >= 2:
                bursts.append({
                    "kind": "burst",
                    "folder": dated[i]["folder"],
                    "when": dated[i]["when"],
                    "until": dated[j - 1]["when"],
                    "media": len(media),
                    "person_ids": sorted(people),
                })
            i = j if j > i + 1 else i + 1

        days: dict[str, dict] = {}
        folders: dict[str, dict] = {}
        for s in sightings:
            if s["when"]:
                day = s["when"][:10]
                d = days.setdefault(day, {"kind": "day", "day": day, "person_ids": set(), "media": set()})
                d["person_ids"].add(s["person_id"])
                d["media"].add(s["media_id"])
            if s["folder"]:
                f = folders.setdefault(
                    s["folder"], {"kind": "folder", "folder": s["folder"], "person_ids": set(), "media": set()}
                )
                f["person_ids"].add(s["person_id"])
                f["media"].add(s["media_id"])

        def _pub(rec):
            out = {k: v for k, v in rec.items() if k not in {"person_ids", "media"}}
            out["person_ids"] = sorted(rec["person_ids"])
            out["people"] = len(rec["person_ids"])
            out["media"] = len(rec["media"])
            return out

        return {
            "bursts": bursts,
            "days": [_pub(days[k]) for k in sorted(days)],
            "folders": [_pub(folders[k]) for k in sorted(folders)],
            "note": "structured signals only; no LLM event titles; not identity",
        }
    finally:
        conn.close()
