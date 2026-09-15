---
name: windows-native
description: Native vs emulated Windows for Semblon. Use when touching runtime detection, ONNX, ARM64, packaging, or docs/runtime.md.
---

# Windows native

- Windows ARM64 native and Windows x64 native are first-class.
- x64 Python or x64 ONNX on ARM64 Windows is `emulated`. Never label that native.
- Record native vs emulated in runtime notes.
- Golden S1 is Windows ARM64 native, ORT 1.30.0, InsightFace 2.0 `buffalo_l`, CPU.
- This machine may run Grok Build as x64-under-Prism. That does not change Semblon's own native/emulated label for identity runs.
