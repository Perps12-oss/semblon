# Decision — local Lens-style retrieval is multi-channel, not a model swap

**Date:** 2026-10-19  
**Status:** current  
**Branch:** `cursor/lens-retrieval-enhancement-4fa1`

## Decision

Semblon will close the remaining local-discovery gap by changing **retrieval structure**, not by replacing the current encoder with a different single vector.

The product act stays `docs/PRODUCT.md`: open a picture, point at a thing, say what a local model can honestly say, and find that visual content in this archive. Public web identification stays out.

The interactive path is:

```text
query understanding (detector + OCR, no describer)
        │
        ▼
parallel recall (dense patches + sparse text + cheap metadata)
        │
        ▼
Reciprocal Rank Fusion
        │
        ▼
lightweight rerank of the fused head
        │
        ▼
optional Name this area / VLM on demand
```

That is the local, low-end-laptop version of the Lens pattern. It is not Google Lens, and it does not claim to be.

## What this does not do

- It does not retune FaceKit / YuNet+SFace, `eps`, or identity thresholds.
- It does not write `faces.person_id` or `embeddings.modality='face'`.
- It does not add schema columns.
- It does not make FAISS, Chroma, YOLO, PaddleOCR, SigLIP-as-index, or a late-interaction GPU reranker a product dependency.
- It does not put a describer (Moondream, Florence, SigLIP naming) on the default similar-search path. **Name this area** stays a button.
- It does not replace DINOv2 content patches with a whole-crop CLIP/SigLIP vector.

## Why not a model swap

A diagnosis of `crop → OpenCLIP single vector → ChromaDB top-k` does not describe `main` as of 2026-10-19. The live similar-region path is DINOv2 patch late-interaction against SQLite embeddings, with colour as a labelled fallback. Screen selection already runs a second merge of region, OCR substring, and NanoDet labels. ANN is named and disabled on purpose (`semblon/index_provider.py`).

Swapping OpenCLIP for SigLIP, or Chroma for FAISS, would still be one retrieval leg. The remaining product gap is that Focus similar-region still often uses only the dense visual leg, text lookup is a longest-token substring, fusion was max-score rather than rank fusion, and there is no cheap rerank of the fused head.

## Authority

- Product contract: `docs/PRODUCT.md`
- Architecture: `docs/ARCHITECTURE.md` (PySide6 → `Application.remember_and_find_region` / `query_media`)
- Schema: `docs/CONTRACTS.md` (no new columns)
- Design: `docs/LENS-RETRIEVAL.md`
- Evidence: `docs/BUILD-STATUS.md`
