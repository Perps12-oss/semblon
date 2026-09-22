# Semblon MSI packaging (code only — no buffalo_l)

**Status:** engineering MSI source + Windows build script **COMPLETE**.  
**Weights:** **UNAVAILABLE** for redistribution until a pack licence exists.  
**Linux agents** can stage/validate; **`wix build` must run on Windows**.

## Layout

| Path | Role |
|------|------|
| `%LOCALAPPDATA%\Programs\Semblon` | MSI code install root (per-user) |
| `%LOCALAPPDATA%\Semblon` | SQLite store + user data — **kept** on MSI uninstall |
| `%USERPROFILE%\.insightface\models\buffalo_l` | May appear after first real ingest via InsightFace — **not** in MSI |

## Owner: build MSI on Windows

```text
cd C:\Users\S8633\Documents\GITHUB\SEMBRON
git fetch origin
git checkout cursor/msi-packaging-dc8c

dotnet tool install --global wix
wix --version

powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
```

Output: `packaging\msi\dist\Semblon-<version>-code.msi`

### Optional Authenticode sign

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignThumbprint <cert-sha1>
```

Requires Windows SDK `signtool`.

### Install / uninstall smoke

See `smoke-checklist.md`.

## What the MSI does **not** do

- Bundle or redistribute `buffalo_l` / `.onnx` identity weights
- Delete `%LOCALAPPDATA%\Semblon` on uninstall (pass checkout `uninstall-windows.ps1 -DeleteStore` only when the human intends to wipe the store)
- Claim a pack licence exists

## First launch

MSI copies code + `.semblon-msi-install` marker. First `semblon.cmd` / Start Menu launch runs `tools\msi\bootstrap-install.ps1` → `install-windows.ps1 -Root <installfolder>` to create `.venv` (requires `py -3.12` on the machine).
