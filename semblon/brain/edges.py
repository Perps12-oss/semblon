"""Graph vocabulary — TEXT columns; enums enforced here, not in SQLite CHECK."""

from __future__ import annotations

VALID_NODE_TYPES = frozenset(
    {
        "Photo",
        "Scene",
        "ObjectCluster",
        "FaceCluster",
        "Person",
        "Tag",
    }
)

# Inc 4 writes only HAS_TAG and HAS_OBJECT. Others reserved for later increments.
VALID_EDGE_TYPES = frozenset(
    {
        "HAS_TAG",
        "HAS_OBJECT",
        "HAS_FACE",
        "HAS_SCENE",
        "CO_OCCURS",
        "SAME_AS",
        "TEMPORAL_NEXT",
        "CONFIRMED_AS",
    }
)

INC4_EDGE_TYPES = frozenset({"HAS_TAG", "HAS_OBJECT"})

VALID_STATUSES = frozenset(
    {
        "candidate",
        "tentative",
        "confirmed",
        "contradicted",
    }
)


def require_node_type(node_type: str) -> str:
    if node_type not in VALID_NODE_TYPES:
        raise ValueError(f"invalid node_type: {node_type!r}")
    return node_type


def require_edge_type(edge_type: str) -> str:
    if edge_type not in VALID_EDGE_TYPES:
        raise ValueError(f"invalid edge_type: {edge_type!r}")
    return edge_type


def require_status(status: str) -> str:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    return status


def normalise_tag_label(label: str) -> str:
    return str(label or "").strip().lower()
