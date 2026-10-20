# Evidence archive

Machine-captured transcripts for Gate B / release blockers. Not a second status tracker — statuses live in `docs/BUILD-STATUS.md`.

| File | What it proves |
|---|---|
| `clean-314-python-version.txt` | Fresh `py -3.14` venv interpreter |
| `clean-314-opencv.txt` | Single headless OpenCV after install scrub |
| `clean-314-pip-freeze.txt` | Declared install freeze (editable excluded) |
| `clean-314-pytest-nonshell.txt` | Non-shell suite on that venv |
| `clean-314-qml-load-before-fix.txt` | Pre-fix failure: `QtMultimedia` missing under Essentials |
| `clean-314-pytest-shell.txt` / `clean-314-pytest-shell-journey.txt` | Shell Focus + Gate A journey after dropping Multimedia import |
| `lens-retrieval-eval.json` | Synthetic Lens rank harness (not confirmatory; precision refused) |

Do not claim Gate C from these files. Signing and redistribution licence remain separate.
