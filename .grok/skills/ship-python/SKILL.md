---
name: ship-python
description: How to run and test Semblon on Windows. Use before claiming a change works.
---

# Ship Python (Semblon)

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
pytest -q
```

- Python 3.11+. Prefer the repo's tested 3.12/3.14 line in `docs/S1-GOLDEN.md` / `docs/runtime.md`.
- No live InsightFace download in unit tests. No real photo dump in CI.
- Do not hit `%USERPROFILE%\.insightface` from pytest.
- Fill `docs/runtime.md` on a machine only when running `lab profile` for FACE-000-class work.
- Quote paths. Never glue `--out` to the next token.
