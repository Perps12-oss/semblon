# Live multi-person overlay (scaffold)

**Status:** experimental / lab only. Engine `live_capture` exists; this is the product surface scaffold.

## What it does

- Tk window (or `--headless`) calls into `live_capture` and draws **bbox + track id + ACCEPT/UNKNOWN** (plus display name on ACCEPT).
- Writes identify **decisions** the same way live already does.
- **Never** writes `faces.person_id` from the overlay.

## How to launch (gated)

Default Home does **not** open this. Use one of:

```text
semblon lab live-overlay --store <path> --source 0 --seconds 10
```

or set `SEMBLON_LIVE_OVERLAY=1` when calling `run_live_overlay(..., explicit_flag=False)`.

Future Home wiring must require `--live-overlay` or `SEMBLON_LIVE_OVERLAY=1` and must not auto-start the webcam.

## Human verify (required before Home)

Before wiring into Home, a human must confirm on **real webcam or RTSP** with **two people** in frame:

1. Two boxes update across frames.
2. Track ids stay stable when people do not cross / leave.
3. Labels show ACCEPT (named gallery hit) and/or UNKNOWN.
4. SQLite: live faces still have `person_id IS NULL`.

Fake-camera unit coverage: `tests/test_live_overlay.py`.
