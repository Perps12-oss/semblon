# Semblon MSI smoke checklist (Windows owner)

Code MSI only. **Do not** expect buffalo_l inside the installer.

## A. Build

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
dir packaging\msi\dist\Semblon-*-code.msi
```

Expect: MSI produced; console says weights NOT included.

## B. Clean install

1. Uninstall any prior Semblon MSI (Settings → Apps).
2. Ensure `%LOCALAPPDATA%\Programs\Semblon` is absent (or empty).
3. Double-click `Semblon-<ver>-code.msi` (per-user; no admin).
4. Confirm Start Menu → **Semblon**.

```text
dir "%LOCALAPPDATA%\Programs\Semblon\semblon.cmd"
dir "%LOCALAPPDATA%\Programs\Semblon\.semblon-msi-install"
```

Expect: **no** `buffalo_l` folder under the install root; **no** `*.onnx` in the install tree.

```text
powershell -NoProfile -Command "Get-ChildItem -Recurse $env:LOCALAPPDATA\Programs\Semblon -Include *.onnx,buffalo_l -ErrorAction SilentlyContinue"
```

Expect: empty.

## C. First launch / bootstrap

Requires Python 3.11–3.13 (`py -3.12`).

```text
"%LOCALAPPDATA%\Programs\Semblon\semblon.cmd" --help
"%LOCALAPPDATA%\Programs\Semblon\semblon.cmd" shell
"%LOCALAPPDATA%\Programs\Semblon\semblon.cmd" lab models
```

Expect: `--help` exit 0; PySide6 archive opens; `lab models` reports weights missing or present under InsightFace cache — not under Programs\Semblon.

## D. Store survives uninstall

```text
dir "%LOCALAPPDATA%\Semblon"
```

Process a tiny stills folder (optional), then uninstall the MSI.

```text
dir "%LOCALAPPDATA%\Programs\Semblon"
dir "%LOCALAPPDATA%\Semblon"
```

Expect: Programs\Semblon gone (or stripped); **`%LOCALAPPDATA%\Semblon` still present** unless the human later runs checkout uninstall with `-DeleteStore`.

## E. Checkout path still works

```text
cd C:\Users\S8633\Documents\GITHUB\SEMBRON
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
.\semblon.cmd --help
```

## Licence honesty

- MSI = application **code** + launchers.
- buffalo_l redistribution = **UNAVAILABLE** (`docs/licenses.md`).
- First ingest does not download buffalo_l. Pin a local pack with `semblon lab pack-accept`.
