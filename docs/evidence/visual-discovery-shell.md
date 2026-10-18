# Visual discovery shell exercise (2026-10-17)

Not a photograph study. Two generated mug images under `docs/evidence/shell-exercise/`.

Offscreen (`QT_QPA_PLATFORM=offscreen`), production `build_shell`:

- Region rows indexed: 4. Face embeddings: 0.
- `setRegion` + `findSimilar`: basis `Similar look`, note `Similar (Similar look): 1 match.`, top `m2`.
- `openDiscoveryHit`: focus `m2`, count stayed 1, basis stayed `Similar look`, day scope empty, back available.
- Second `findSimilar` on the opened photo: still `Similar look`, 1 match.
- Sqlite reopen: 4 region rows. Sidecar `shell.visual-discovery.json` present.

Visible window (`QT_QPA_PLATFORM=windows`), same store, same search:

- Basis `Similar look`, note `Similar (Similar look): 1 match.`, count 1.
- Grab: `docs/evidence/visual-discovery-shell-windows.png` (1800×1125). The window shows the mug, the drawn rectangle, the **Similar look** button, and the line `Similar (Similar look): 1 match.`
- Offscreen grab `docs/evidence/visual-discovery-shell-offscreen.png` did not paint readable text.

Runtime: Windows ARM64 host, emulated x64 `.venv-312` (PE `0x8664`). Not native ARM64.
