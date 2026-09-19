# SEMBLON — Licence record

InsightFace code is typically MIT. buffalo_l weights often research/non-commercial.
FACE-000–003 = internal evaluation only. Not commercial permission.
Shipping weights needs a separate licence/pack decision. Fallback: YuNet + SFace.
Do not block FACE-000 on that decision.
Do not bundle buffalo_l into a frozen installer until that decision exists. `tools/install-windows.ps1` installs code only.

Future candidates (MediaPipe, CLIP/successors, other packs) need a separate code **and** model licence check before they enter the plan as more than a name. A licence veto beats a technically attractive model. See `docs/SEMBLON_MATURITY_BLUEPRINT.md` §1.3.

PySide6 / Qt 6 (S8 toolkit spike only): **LGPL**. Dynamic link from optional extra `.[gui]`. Not a core dependency. Do not statically link Qt without a separate licence pass. See `docs/S8-TOOLKIT.md`.
