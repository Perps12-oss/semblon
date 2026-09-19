# Packaging

**Engineering:** checkout install via `tools/install-windows.ps1`.  
**Verification:** HUMAN VERIFICATION REQUIRED for clean-machine UX.  
**Redistribution of buffalo_l:** UNAVAILABLE pending licence.

## Supported install (code)

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

## Not in this release

- MSI / frozen exe / PyInstaller bundle of buffalo_l
- Silent commercial redistribution of InsightFace weights

## Smoke procedure (human)

1. Clean directory, run `install-windows.ps1`
2. `semblon.cmd --help` exits 0
3. `semblon.cmd home` opens the window
4. Process a small stills folder; Open Review; Name one cluster
5. `semblon.cmd lab integrity --store "%LOCALAPPDATA%\Semblon\store.sqlite"`
