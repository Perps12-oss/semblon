"""Vector-index seam. SQLite embeddings stay authoritative.

The active provider is the exact derived matrix in ``ann_index``. That scan is
a dot product over normalised rows, not an approximate nearest-neighbour index.

An ANN provider is intentionally unwired. FAISS, Chroma, and any other
approximate index stay out of the product until a measurement shows the
library scan is the bottleneck. Adding one later means a new provider behind
``active_vector_index``, not a second search stack.
"""

from __future__ import annotations

from pathlib import Path


class ExactDerivedIndex:
    """Exact derived matrix. The library remains the source of truth."""

    name = "exact-derived"

    def ready(self, store: Path) -> bool:
        from semblon.ann_index import has_index

        return has_index(store)

    def search(
        self,
        store: Path,
        *,
        item_id: str,
        modality: str,
        pack_id: str,
        vector: bytes,
        dim: int,
        limit: int,
    ) -> list[dict] | None:
        from semblon.ann_index import search_index

        return search_index(
            store,
            item_id=item_id,
            modality=modality,
            pack_id=pack_id,
            vector=vector,
            dim=dim,
            limit=limit,
        )


def active_vector_index() -> ExactDerivedIndex:
    """The only index the product searches with today."""
    return ExactDerivedIndex()


def index_seam_status() -> dict:
    """Honest seam state. ANN is named and disabled."""
    return {
        "active": ExactDerivedIndex.name,
        "authoritative": "sqlite",
        "approximate": False,
        "ann": {
            "enabled": False,
            "reason": (
                "ANN is not wired. Add a provider behind active_vector_index "
                "only after a measured retrieval bottleneck."
            ),
        },
    }
