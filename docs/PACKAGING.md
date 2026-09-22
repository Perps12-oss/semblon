# Packaging

**Engineering:** checkout install via `tools/install-windows.ps1`, or per-user **code MSI** via `packaging/msi` (WiX).  
**Verification:** HUMAN VERIFICATION REQUIRED for clean-machine UX (`packaging/msi/smoke-checklist.md`).  
**Redistribution of buffalo_l:** **UNAVAILABLE** pending pack licence — never bundled in MSI/installer.

## Supported install (code) — checkout

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
semblon.cmd --help
semblon.cmd home
```

Does not bundle model weights. First real ingest may download buffalo_l into `%USERPROFILE%\.insightface\models\buffalo_l` via InsightFace.

Check weights without downloading:

```text
semblon.cmd lab models
```

## Supported install (code) — MSI

WiX project: `packaging/msi/Semblon.wxs` + generated `PayloadComponents.wxs`.  
Windows owner build (this Linux/cloud agent cannot run `wix build`):

```text
dotnet tool install --global wix
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
```

Output: `packaging\msi\dist\Semblon-<version>-code.msi`

| Path | Role |
|------|------|
| `%LOCALAPPDATA%\Programs\Semblon` | MSI code install (per-user) |
| `%LOCALAPPDATA%\Semblon` | Store — **survives** MSI uninstall |
| Install tree `*.onnx` / `buffalo_l` | **Must be absent** |

First launch bootstraps `.venv` when `.semblon-msi-install` is present (`tools/msi/bootstrap-install.ps1`). Requires `py -3.12` on the machine.

Optional sign:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignThumbprint <cert-sha1>
```

Details: `packaging/msi/README.md`. Smoke: `packaging/msi/smoke-checklist.md`.

## Upgrade / uninstall

`tools/install-windows.ps1` reuses `.venv` and does **not** touch `%LOCALAPPDATA%\Semblon`.  
`tools/uninstall-windows.ps1` removes `.venv` and keeps the store unless `-DeleteStore`.  
MSI uninstall removes `%LOCALAPPDATA%\Programs\Semblon` only — **not** the store.

## Licence boundary

| Artifact | Status |
|----------|--------|
| Code MSI / checkout install | Engineering path shipped |
| buffalo_l inside MSI / frozen exe | **UNAVAILABLE** — `docs/licenses.md` |
| First-ingest InsightFace download into user profile | Possible; not redistribution by Semblon installer |

## Not in this release

- MSI / frozen exe / PyInstaller bundle of buffalo_l
- Silent commercial redistribution of InsightFace weights

## Smoke procedure (human) — checkout

1. Clean directory, run `install-windows.ps1`
2. `semblon.cmd --help` exits 0
3. `semblon.cmd home` opens the window
4. Process a small stills folder; Open Review; Name one cluster
5. `semblon.cmd lab integrity --store "%LOCALAPPDATA%\Semblon\store.sqlite"`

## Smoke procedure (human) — MSI

Follow `packaging/msi/smoke-checklist.md` (build → install → no weights in tree → store survives uninstall).
