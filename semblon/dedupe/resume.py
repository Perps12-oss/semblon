"""Resume support: a scan checkpoint is just the hash cache plus the discovery manifest.

Re-running ``scan_exact`` with the same cache skips every file whose (path, size, mtime) is
unchanged. Persistence to a ``<store stem>.dedupe.sqlite`` sidecar is a later phase; this module
only provides the JSON-serialisable shape.
"""

from __future__ import annotations

from .discovery import DirRecord, DiscoveryManifest
from .hashing import MemoryHashCache

CHECKPOINT_VERSION = 1


def to_checkpoint(cache: MemoryHashCache, manifest: DiscoveryManifest | None = None) -> dict:
    return {
        "version": CHECKPOINT_VERSION,
        "hashes": cache.export(),
        "manifest": None
        if manifest is None
        else {
            "fingerprint": manifest.fingerprint,
            "dirs": {
                k: [r.mtime_ns, r.files, r.subdirs] for k, r in manifest.dirs.items()
            },
        },
    }


def from_checkpoint(data: dict) -> tuple[MemoryHashCache, DiscoveryManifest | None]:
    if not isinstance(data, dict) or data.get("version") != CHECKPOINT_VERSION:
        return MemoryHashCache(), None
    cache = MemoryHashCache.load(data.get("hashes") or [])
    m = data.get("manifest")
    manifest = None
    if m:
        manifest = DiscoveryManifest(
            fingerprint=m.get("fingerprint", ""),
            dirs={k: DirRecord(int(v[0]), list(v[1]), list(v[2])) for k, v in m["dirs"].items()},
        )
    return cache, manifest
