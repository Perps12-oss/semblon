# Semblon — product contract

**Status:** enduring contract. Implementation gaps do not amend this file.  
**Evidence date of the split:** 2026-10-16. Centre-of-gravity correction: 2026-10-18.  
**What exists today:** `docs/BUILD-STATUS.md`.  
**What closes the gap:** `docs/ROADMAP.md`.  
**Why the wording changed:** `docs/decisions/2026-10-16-product-truth-layers.md`, `docs/decisions/2026-10-18-local-visual-discovery.md`.

Semblon is a local visual memory you can look into. The defining act is to open something from your own archive, point at a thing in it, and find that thing again in your other pictures. The archive, people, time, and folders support that act. Faces are one capability, not the product identity. Uncertain identity remains uncertain. A local model does not invent a product, landmark, or species name. Processing and capability availability are represented honestly.

## Who it is for

One person. One Windows machine. Their files stay where they are. SQLite and the original files are authoritative. There is no cloud account, no shared library, and no ACC.

Windows x64 native and Windows ARM64 native are both first-class. x64-on-ARM64 is emulated, and the product says so.

## Principles

1. Point, understand, and find is the product. The archive holds the pictures. People, time, appearance, text, and other signals support looking into that same archive.
2. Unknown is a valid result. A false merge is worse than a false split. A wrong identity is worse than unknown.
3. A cluster, a track, a hypothesis, a review decision, and a named person are different things. Naming is a human act.
4. A missing model, a missing file, and an empty match are different outcomes. The product says which one happened.
5. Optional models stay optional. Colour, contours, text, and semantics do not silently become identity.
6. Local-first includes honest offline behaviour. Semblon does not fetch identity weights on first use.

## Intended workflows

These are the product, including where the build is still short of them. Shortfalls are recorded in `docs/BUILD-STATUS.md`. They do not shrink this list.

1. **Enter the archive.** Add a folder. See an honest empty state, then a thumbnail grid. Open a photo and inspect it. File references survive moves and renames.
2. **Look into a picture.** Open a supported visual. Point at a thing, or draw around it, and get a selection that follows that thing. Semblon says what it can say: text, a face, a class the installed detector actually returned, or an unlabelled region. It then searches this archive for other pictures where that visual content appears, including another angle or different light. Each result shows where the match sits. Opening a result keeps the search so you can point again. A missing model, a picture that was never indexed, and a genuine empty match stay different outcomes.
3. **Recover the context.** From a result, reach the date, the surrounding photos, and the related moments.
4. **Keep a discovery.** Save a useful find, return to it, and keep the picture, the selection, and the matches it came from.
5. **Trust the library.** Review people when that is useful. Correct a decision. Erase a person or the library without deleting the original files. Install and run on a clean Windows machine with a signed, versioned package.

Identity review, when used, follows `cluster → review → person → name`. A cluster id is never a person id.

## Privacy

The library holds paths, display names, and biometric templates. That is special-category data for this one user.

- Originals are not deleted by reset, person erase, or library wipe.
- Erase is explicit. The archive does not expire on its own.
- Backups are copies of the store. A synced folder is not a private store.
- Encryption at rest is part of the trust requirement for a non-author install. Until it exists, the threat model says the store is plaintext. See `docs/THREAT-MODEL.md`.

## What success is

A person can add their own photos, open one, point at a thing, read an honest account of that selection, and find other photos in the archive where that visual content appears, with the matching place marked. They can continue from a result and keep the find. Identity stays uncertain until they name someone. Every signal that is not installed says so. The same archive is still there after a move, a correction, or an erase.

## Out of the product

Public lookup, live CCTV as a product, a shared or multi-user library, mobile, automatic identity, and a second identity engine. Folder watching is not the Add folder action. Research tools (`tools/s8_toolkit_spike`, the Live overlay) are not the product shell.

## Architecture that serves this contract

The production UI is the PySide6 archive (`semblon shell`) on `Application`. That choice is closed in `docs/ARCHITECTURE.md`. This contract does not reopen it.

FaceKit / InsightFace is the only identity engine. `pack_id` includes weight hashes. Geometry, colour, objects, and semantics do not vote on identity. Identity thresholds stay frozen (`docs/S1-GOLDEN.md`).

Schema and runtime contracts stay in `docs/CONTRACTS.md`. Engineering planned work stays in `docs/SEM-ARCH-V1.4.md`. Neither file redefines this contract.

## How documents stay apart

| Document | Job |
|---|---|
| `docs/PRODUCT.md` | This contract |
| `docs/BUILD-STATUS.md` | What the checkout actually does, with evidence |
| `docs/ROADMAP.md` | Ordered outcomes that close the gap |
| `docs/decisions/` | Why direction changed, and the text that used to be current |
| `docs/ARCHITECTURE.md` | Closed production architecture |
| `docs/SHELL-IA.md` | Historical Tk Home information architecture |
| `docs/TIMELINE-VIEW.md` | Current production shell chrome |
| `docs/UI-EXPOSURE-MAP.md` | Exposure inventory; historical sections are marked |
