"""BRAIN — capability arbitration over local evidence.

Increment 1–3: inventory, evidence, NanoDet adopt, face suggest.
Increment 4: Tag/Photo/ObjectCluster graph (batch).
"""

from __future__ import annotations

from semblon.brain.adoption import (
    adopt_existing_nanodet_tags,
    adopt_existing_object_dbscan,
)
from semblon.brain.benchmark import BenchmarkResult, BrainBenchmark
from semblon.brain.cache import EvidenceCache, PersistEvidenceCache
from semblon.brain.confidence import CONFIDENCE_MODEL_VERSION
from semblon.brain.edges import INC4_EDGE_TYPES, VALID_EDGE_TYPES, VALID_NODE_TYPES
from semblon.brain.evidence import EvidenceExplanation, WriteResult, explain, record_observations
from semblon.brain.face_suggest import FaceSuggestObserver, SuggestResult, run_face_suggest
from semblon.brain.graph import sync_tags_from_observations
from semblon.brain.nanodet_observer import NanoDetObserver
from semblon.brain.object_cluster import rebuild_object_clusters
from semblon.brain.observation import Observation, PhotoRef, Region
from semblon.brain.observer import BrainObserver
from semblon.brain.pipeline import BrainPipeline, PipelineResult
from semblon.brain.policy import BrainPolicy, Selection, SelectionContext
from semblon.brain.registry import CapabilityRegistry, ProviderRecord

__all__ = [
    "CONFIDENCE_MODEL_VERSION",
    "INC4_EDGE_TYPES",
    "VALID_EDGE_TYPES",
    "VALID_NODE_TYPES",
    "BenchmarkResult",
    "BrainBenchmark",
    "BrainObserver",
    "BrainPipeline",
    "BrainPolicy",
    "CapabilityRegistry",
    "EvidenceCache",
    "EvidenceExplanation",
    "FaceSuggestObserver",
    "NanoDetObserver",
    "Observation",
    "PersistEvidenceCache",
    "PhotoRef",
    "PipelineResult",
    "ProviderRecord",
    "Region",
    "Selection",
    "SelectionContext",
    "SuggestResult",
    "WriteResult",
    "adopt_existing_nanodet_tags",
    "adopt_existing_object_dbscan",
    "explain",
    "record_observations",
    "rebuild_object_clusters",
    "run_face_suggest",
    "sync_tags_from_observations",
]
