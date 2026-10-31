# Semblon code MSI — signing gate (D.4 engineering runbook)

**Purpose:** What must be signed, how to timestamp, and how to verify.  
**Not Gate C PASS** until a clean-machine SmartScreen check and `packaging/msi/smoke-checklist.md` (or `smoke-clean-vm.ps1`) are done by the owner.  
**No secrets** in this file. Do not store PFX bytes, passwords, or private keys in the repo.

## Scope

Sign the **code MSI** artifact only:

- `packaging/msi/dist/Semblon-*-code.msi`

The MSI must contain **no** `.onnx` / buffalo_l weights (`tools/msi/assert-no-weights.py`). Offline-bundle MSIs with weights are **out of ship**.

Optional: if a frozen `semblon.exe` / runtime DLLs are produced later, sign those with the same rules. Today’s WiX payload is a per-user code install + launcher (see `docs/PACKAGING.md`).

## How Semblon signs today

Local (`tools/msi/build-msi.ps1`):

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignThumbprint <cert-sha1>
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignPfxPath path\to\cert.pfx -SignPfxPassword <secret>
```

CI (`.github/workflows/msi-release.yml`, `workflow_dispatch`):

- Secrets (optional): `CODE_SIGNING_PFX_BASE64`, `CODE_SIGNING_PFX_PASSWORD`
- Sign: `signtool sign /f … /fd SHA256 /tr http://timestamp.digicert.com /td SHA256`
- Verify: `signtool verify /pa /v <msi>`

That `/tr` URL is an **RFC 3161** timestamp server (DigiCert). Prefer RFC 3161 over legacy Authenticode-only timestamp endpoints.

## Pass criteria (engineering)

1. `signtool verify /pa` succeeds on the MSI.
2. Publisher identity matches the certificate the owner registered.
3. Clean Win10/Win11 VM: no full SmartScreen block that forces “Run anyway” for an unknown publisher (reputation can lag for new OSS publishers — run early).
4. Smoke: `packaging/msi/smoke-clean-vm.ps1` / `smoke-checklist.md` — install tree has **no** `.onnx`.

Unsigned CI uploads are **engineering builds only**, not Gate C.

## Forbidden

- PFX / password / private key in git, workflow YAML, or this document
- Claiming Gate C or Gate L PASS from signing alone
- Shipping identity / region / object ONNX inside the default MSI
