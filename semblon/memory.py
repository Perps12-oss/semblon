"""S6 visual memory: when / where / with whom. Read-only. Not identity.

Does not invent schema columns. Time comes from EXIF, filename, or mtime_ns.
Place is folder path plus GPS if EXIF has it. No geocoding. No CLIP.
Time and place must not change compare() or cluster membership.
"""

from __future__ import annotations

import json
import re
import sqlite3
import struct
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from semblon.store import connect_readonly

BURST_NS = 90 * 1_000_000_000
_FN_TIME = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})")


class MemoryError(ValueError):
    pass


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise MemoryError(f"store not found: {p}")
    conn = connect_readonly(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
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


def _folder_name(path: str) -> str | None:
    """Parent folder. Splits on / and \\ so Windows paths work off Windows."""
    if not path:
        return None
    parts = [p for p in str(path).replace("\\", "/").rstrip("/").split("/") if p]
    if len(parts) < 2:
        return None
    return parts[-2]


def _filename_when_ns(path: str) -> int | None:
    name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    m = _FN_TIME.search(name)
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
    """Naive local EXIF timestamp. Do not label it UTC without an offset."""
    try:
        s = raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except (ValueError, UnicodeError):
        return None


def _parse_exif_offset(raw: bytes) -> timedelta | None:
    """EXIF OffsetTime* ASCII ±HH:MM. None when the field is missing or malformed."""
    try:
        s = raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    except UnicodeError:
        return None
    m = re.fullmatch(r"([+-])(\d{2}):(\d{2})", s)
    if not m:
        return None
    hours, minutes = int(m.group(2)), int(m.group(3))
    if hours > 14 or minutes > 59:
        return None
    sign = 1 if m.group(1) == "+" else -1
    return timedelta(minutes=sign * (hours * 60 + minutes))


def _exif_ascii(app1: bytes, endian: str, count: int, val: bytes) -> bytes | None:
    if count <= 0:
        return None
    if count <= 4:
        return val[:count]
    voff = struct.unpack(endian + "I", val)[0]
    if voff < 0 or voff + count > len(app1):
        return None
    return app1[voff : voff + count]


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
    """Best-effort JPEG EXIF. Empty dict if missing, unreadable, or not JPEG."""
    p = Path(path)
    try:
        if not p.is_file():
            return {}
        with p.open("rb") as fh:
            if fh.read(2) != b"\xff\xd8":
                return {}
            app1 = None
            while True:
                b = fh.read(1)
                if not b:
                    break
                if b != b"\xff":
                    continue
                # Fill 0xFF is padding, not a marker. Standalone markers have no length.
                marker = fh.read(1)
                while marker == b"\xff":
                    marker = fh.read(1)
                if not marker:
                    break
                code = marker[0]
                if code in (0xDA, 0xD9):  # SOS, EOI
                    break
                if code == 0x01 or code == 0x00 or 0xD0 <= code <= 0xD8:
                    continue
                seglen_raw = fh.read(2)
                if len(seglen_raw) != 2:
                    break
                seglen = struct.unpack(">H", seglen_raw)[0]
                if seglen < 2:
                    break
                payload = fh.read(seglen - 2)
                if marker == b"\xe1" and payload.startswith(b"Exif\x00\x00"):
                    app1 = payload[6:]
                    break
    except (OSError, struct.error):
        return {}
    if not app1 or len(app1) < 8:
        return {}
    endian = "<" if app1[:2] == b"II" else ">"
    ifd0 = struct.unpack(endian + "I", app1[4:8])[0]
    out: dict = {}
    exif_off = gps_off = None
    naive: dict[str, datetime] = {}
    offsets: dict[str, timedelta] = {}

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
            elif tag in (0x0132, 0x9003, 0x9004) and typ == 2:
                raw = _exif_ascii(app1, endian, cnt, val)
                dt = _parse_exif_datetime(raw or b"")
                if dt is not None:
                    key = {
                        0x9003: "datetime_original",
                        0x9004: "datetime_digitized",
                    }.get(tag, "datetime")
                    naive[key] = dt
            elif tag in (0x9010, 0x9011, 0x9012) and typ == 2:
                raw = _exif_ascii(app1, endian, cnt, val)
                off_td = _parse_exif_offset(raw or b"")
                if off_td is not None:
                    key = {
                        0x9011: "datetime_original",
                        0x9012: "datetime_digitized",
                    }.get(tag, "datetime")
                    offsets[key] = off_td

    try:
        read_ifd(ifd0)
        if exif_off:
            read_ifd(exif_off)
        for key, dt in naive.items():
            off_td = offsets.get(key)
            if off_td is None and key != "datetime":
                off_td = offsets.get("datetime")
            if off_td is None:
                # Local wall time with no offset is not a UTC instant.
                out[key] = dt.isoformat()
                continue
            utc = (dt.replace(tzinfo=timezone.utc) - off_td).astimezone(timezone.utc)
            out[key] = utc.isoformat()
            out[key + "_ns"] = _dt_to_ns(utc)
    except (struct.error, ValueError):
        return {}
    try:
        _read_gps(app1, endian, gps_off, out)
    except struct.error:
        return out
    return out


def _read_gps(app1: bytes, endian: str, gps_off, out: dict) -> None:
    if not gps_off or gps_off + 2 > len(app1):
        return
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


def when_where(
    path: str,
    mtime_ns: int | None,
    *,
    t_ms: int | None = None,
    source_type: str | None = None,
) -> dict:
    exif = {}
    if path and source_type not in {"video", "live"}:
        exif = _read_still_exif_cached(str(path), int(mtime_ns) if mtime_ns else 0)
    ns = exif.get("datetime_original_ns") or exif.get("datetime_ns")
    source = "exif"
    if ns is None:
        ns = _filename_when_ns(path)
        source = "filename"
    if ns is None:
        ns = int(mtime_ns) if mtime_ns else None
        source = "mtime"
    if source_type == "video" and t_ms is not None and ns is not None:
        ns = int(ns) + int(t_ms) * 1_000_000
    rec = {
        "when_ns": ns,
        "when": datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat() if ns else None,
        "when_source": source if ns else None,
        "folder": _folder_name(path) if path else None,
        "path": path,
    }
    if "lat" in exif:
        rec["lat"] = exif["lat"]
        rec["lon"] = exif["lon"]
        rec["place_source"] = "exif_gps"
    else:
        rec["place_source"] = "folder"
    return rec


@lru_cache(maxsize=8192)
def _read_still_exif_cached(path: str, mtime_ns: int) -> dict:
    return read_still_exif(Path(path))


def _named_rows(conn, run_id: str | None, person_id: str | None):
    sql = """
        SELECT f.face_id, f.person_id, f.status, f.size_band, f.face_w, f.face_h,
               p.display_name, m.media_id, m.path, m.mtime_ns, m.source_type,
               o.frame_id, o.t_ms
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


def _sighting(r, *, with_person: bool = False) -> dict:
    ww = when_where(
        r["path"],
        r["mtime_ns"],
        t_ms=r["t_ms"],
        source_type=r["source_type"],
    )
    rec = {
        "face_id": r["face_id"],
        "media_id": r["media_id"],
        "size_band": r["size_band"],
        "source_type": r["source_type"],
        "frame_id": r["frame_id"],
        "t_ms": r["t_ms"],
        **ww,
    }
    if with_person:
        rec["person_id"] = r["person_id"]
        rec["display_name"] = r["display_name"]
    return rec


def _presence(items: list[dict]) -> list[dict]:
    """Per-media video interval for one named person. Stills stay on items."""
    by_media: dict[str, list[dict]] = {}
    for it in items:
        if it.get("source_type") != "video":
            continue
        by_media.setdefault(it["media_id"], []).append(it)
    out = []
    for media_id, rows in by_media.items():
        with_t = sorted(
            (r for r in rows if r.get("t_ms") is not None),
            key=lambda r: (int(r["t_ms"]), r["face_id"]),
        )
        frames = [r["frame_id"] for r in with_t if r.get("frame_id") is not None]
        first = min(rows, key=lambda r: (r["when_ns"] is None, r["when_ns"] or 0, r["face_id"]))
        out.append({
            "media_id": media_id,
            "path": first["path"],
            "source_type": "video",
            "folder": first["folder"],
            "t_ms_start": with_t[0]["t_ms"] if with_t else None,
            "t_ms_end": with_t[-1]["t_ms"] if with_t else None,
            "frame_id_start": frames[0] if frames else None,
            "frame_id_end": frames[-1] if frames else None,
            "sightings": len(rows),
            "when_ns": first["when_ns"],
            "when": first["when"],
            "when_source": first["when_source"],
        })
    out.sort(key=lambda x: (x["when_ns"] is None, x["when_ns"] or 0, x["media_id"]))
    return out


def history(store: Path, *, person: str, run_id: str | None = None) -> dict:
    """Person × time/place, including named video presence. Does not identify. Does not write."""
    conn = _connect_ro(store)
    try:
        prow = _require_person(conn, person)
        rows = _named_rows(conn, run_id, prow["person_id"])
        items = [_sighting(r) for r in rows]
        items.sort(key=lambda x: (x["when_ns"] is None, x["when_ns"] or 0, x["face_id"]))
        return {
            "person_id": prow["person_id"],
            "display_name": prow["display_name"],
            "sightings": len(items),
            "items": items,
            "presence": _presence(items),
            "note": "S6 memory; not identity. Time/place do not change pack_id compare.",
        }
    finally:
        conn.close()


def together(store: Path, *, run_id: str | None = None) -> dict:
    """Named people on the same still or video clip. Cluster is not a person."""
    conn = _connect_ro(store)
    try:
        rows = _named_rows(conn, run_id, None)
        by_media: dict[str, dict] = {}
        for r in rows:
            rec = by_media.setdefault(
                r["media_id"],
                {
                    "media_id": r["media_id"],
                    "path": r["path"],
                    "mtime_ns": r["mtime_ns"],
                    "source_type": r["source_type"],
                    "t_vals": [],
                    "people": {},
                },
            )
            rec["people"][r["person_id"]] = r["display_name"]
            if r["t_ms"] is not None:
                rec["t_vals"].append(int(r["t_ms"]))
        derived_by_media: dict[str, dict] = {}
        for rec in by_media.values():
            people = rec["people"]
            if len(people) < 2:
                continue
            t_ms = min(rec["t_vals"]) if rec["t_vals"] else None
            ww = when_where(
                rec["path"],
                rec["mtime_ns"],
                t_ms=t_ms,
                source_type=rec["source_type"],
            )
            ids = sorted(people)
            item = {
                "media_id": rec["media_id"],
                "person_ids": ids,
                "names": [people[i] for i in ids],
                "source_type": rec["source_type"],
                **ww,
            }
            if rec["source_type"] == "video" and rec["t_vals"]:
                item["t_ms_start"] = min(rec["t_vals"])
                item["t_ms_end"] = max(rec["t_vals"])
            derived_by_media[rec["media_id"]] = item

        snap_rows = conn.execute(
            """
            SELECT evidence_json, confirmed
            FROM relationships
            WHERE kind='together'
            """
            + (" AND run_id=?" if run_id else ""),
            ([run_id] if run_id else []),
        ).fetchall()
        pairs: list[dict] = []
        seen: set[str] = set()
        for row in snap_rows:
            evidence = {}
            try:
                evidence = json.loads(row["evidence_json"] or "{}")
            except json.JSONDecodeError:
                evidence = {}
            ids = sorted([str(x) for x in (evidence.get("person_ids") or []) if x])
            if len(ids) < 2:
                continue
            media_id = evidence.get("media_id")
            key = str(media_id) if media_id else "|".join(ids)
            if key in seen:
                continue
            base = derived_by_media.get(media_id or "")
            if base is None:
                mrow = None
                if media_id:
                    mrow = conn.execute(
                        "SELECT media_id, path, mtime_ns, source_type FROM media WHERE media_id=?",
                        (media_id,),
                    ).fetchone()
                if mrow:
                    ww = when_where(mrow["path"], mrow["mtime_ns"], source_type=mrow["source_type"])
                    base = {"media_id": mrow["media_id"], "source_type": mrow["source_type"], **ww}
                else:
                    base = {"media_id": media_id, "source_type": evidence.get("source_type")}
            names = evidence.get("names") or base.get("names") or ids
            item = {
                "media_id": base.get("media_id"),
                "person_ids": ids,
                "names": names,
                "source_type": base.get("source_type"),
                "when_ns": base.get("when_ns"),
                "when": base.get("when"),
                "when_source": base.get("when_source"),
                "folder": base.get("folder"),
                "path": base.get("path"),
                "snapshot_confirmed": int(row["confirmed"] or 0),
            }
            if base.get("t_ms_start") is not None:
                item["t_ms_start"] = base.get("t_ms_start")
                item["t_ms_end"] = base.get("t_ms_end")
            pairs.append(item)
            seen.add(key)

        for media_id, item in derived_by_media.items():
            if media_id in seen:
                continue
            pairs.append(item)
        pairs.sort(key=lambda x: (x["when_ns"] is None, x["when_ns"] or 0, x.get("media_id") or ""))
        return {
            "pairs": len(pairs),
            "items": pairs,
            "note": "co-appearance on one media (snapshot + derived union); not a cluster merge",
        }
    finally:
        conn.close()


def events(store: Path, *, run_id: str | None = None) -> dict:
    """Structured events: burst, day, folder. No LLM titles."""
    conn = _connect_ro(store)
    try:
        rows = _named_rows(conn, run_id, None)
        sightings = [_sighting(r, with_person=True) for r in rows]
        # Bursts: same folder, adjacent times within BURST_NS, 2+ media.
        dated = [s for s in sightings if s["when_ns"] is not None]
        dated.sort(key=lambda s: (s["folder"] or "", s["when_ns"], s["media_id"]))
        bursts = []
        i = 0
        while i < len(dated):
            j = i + 1
            media = {dated[i]["media_id"]}
            people = {dated[i]["person_id"]}
            start_ns = dated[i]["when_ns"]
            while (
                j < len(dated)
                and dated[j]["folder"] == dated[i]["folder"]
                and dated[j]["when_ns"] - start_ns <= BURST_NS
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
                    "media_ids": sorted(media),
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
            # Publish ids for Moments / Timeline browse facets (not identity).
            out["media_ids"] = sorted(rec["media"])
            return out

        snap_rows = conn.execute(
            """
            SELECT label, t_start, t_end, folder, evidence_json, confirmed
            FROM events
            """
            + (" WHERE run_id=?" if run_id else ""),
            ([run_id] if run_id else []),
        ).fetchall()
        snapshot_events: list[dict] = []
        snap_burst_keys: set[tuple] = set()
        merged_bursts: list[dict] = []
        for row in snap_rows:
            evidence = {}
            try:
                evidence = json.loads(row["evidence_json"] or "{}")
            except json.JSONDecodeError:
                evidence = {}
            ev = {
                "kind": row["label"] or evidence.get("kind"),
                "folder": row["folder"] or evidence.get("folder"),
                "when": row["t_start"] or evidence.get("when"),
                "until": row["t_end"] or evidence.get("until"),
                "confirmed": int(row["confirmed"] or 0),
            }
            if "person_ids" in evidence:
                ev["person_ids"] = evidence.get("person_ids") or []
            if "media" in evidence:
                ev["media"] = evidence.get("media")
            if "media_ids" in evidence:
                ev["media_ids"] = list(evidence.get("media_ids") or [])
            snapshot_events.append(ev)
            if ev["kind"] == "burst":
                key = (ev.get("kind"), ev.get("folder"), ev.get("when"), ev.get("until"))
                snap_burst_keys.add(key)
                merged_bursts.append(ev)

        for b in bursts:
            key = (b.get("kind"), b.get("folder"), b.get("when"), b.get("until"))
            if key in snap_burst_keys:
                continue
            merged_bursts.append(b)

        return {
            "bursts": merged_bursts,
            "days": [_pub(days[k]) for k in sorted(days)],
            "folders": [_pub(folders[k]) for k in sorted(folders)],
            "snapshots": snapshot_events,
            "note": "structured signals only (snapshot + derived union); no LLM event titles; not identity",
        }
    finally:
        conn.close()
