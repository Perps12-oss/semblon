# Threat model

Semblon is one user on one Windows machine. The sensitive asset is the library store: display names, file paths, and 512-d face templates in `store.sqlite`.

## What the store is protected against

- Other Windows users, by the ACL on `%LOCALAPPDATA%`.
- A crash during schema migration 4 dropping `decisions` and then refusing to open. Migration 4 is one transaction, and a leftover `decisions_new` is finished on the next open.
- A restore that deletes the live database before the backup copy finishes. The copy lands in a temp file and replaces the live file only after that copy succeeds.
- Silent download of `buffalo_l`. Ingest loads a pack only after `semblon lab pack-accept` pins the local ONNX hashes.

## What it is not protected against

- Malware running as the same user.
- A backup written into a folder that syncs. `backup` is a raw SQLite copy: names, paths, and embeddings.
- A stolen disk. The store is plaintext. SQLCipher or a DPAPI-wrapped file is not implemented; adding it needs a design that keeps WAL and the existing library intact.

## Erasure

`semblon erase person --person <id>` deletes that person, their face rows, embeddings, decisions, and cluster links. It does not delete the original photo.

`semblon erase library --yes` deletes library rows. It does not delete original files and it is not Reset. Reset still clears preferences and caches and keeps the library.

Live capture has a retention window. The archive does not expire on its own; erasure is explicit.
