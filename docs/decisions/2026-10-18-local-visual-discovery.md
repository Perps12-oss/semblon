# Decision — local visual discovery is the product

**Date:** 2026-10-18  
**Status:** current  
**Branch:** `grok/local-lens`

## Decision

Semblon's defining act is local visual discovery across one person's own archive: open a picture, point at a thing, say what a local model can honestly say, and find that visual content in other pictures in the archive.

The archive, people review, time, and folders stay. They support that act. They are not a second product.

This amends the centre of gravity in `docs/PRODUCT.md`. It does not reopen `docs/ARCHITECTURE.md`, identity thresholds, or the identity firewall. Geometry, colour, objects, text, and region matches do not write `faces.person_id` or `embeddings.modality='face'`.

## What “understand” means here

A selection can be reported as text, a face, a class the installed detector actually returned, or an unlabelled region. Semblon does not invent a product name, a landmark, or a species. Public lookup stays out of the product.

## What retrieval must do

A pointed region must be searchable even when that content was not one of the pre-indexed proposal boxes. The implementation is a dense DINOv2 patch map (one forward over the whole frame, every content patch stored) scored with late interaction against the query crop. Proposal crops remain only as a fallback when that map is absent.

Match results carry the place in the other photo. A find can be kept beside the library without a new table. Identity review is unchanged.

## What this decision does not do

It does not claim Google's web identification. It does not retune FaceKit or SFace. It does not add schema columns. It does not replace the PySide6 shell.
