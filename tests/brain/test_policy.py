"""BrainPolicy: reuse / skip / invoke / defer without loading models."""

from __future__ import annotations

from semblon.brain.cache import EvidenceCache
from semblon.brain.observation import Observation, PhotoRef
from semblon.brain.policy import BrainPolicy, SelectionContext, load_policy_yaml


def _photo(pid: str = "p1") -> PhotoRef:
    return PhotoRef(photo_id=pid, content_hash="sha-p1")


def test_load_policy_yaml_preferences():
    cfg = load_policy_yaml()
    assert cfg["C1_tag_generic"]["preference"][0] == "existing_nanodet_tags"
    assert cfg["C6_search_similar"]["preference"] == ["existing_index"]
    assert "faiss" not in str(cfg).lower()
    assert cfg["C8_scene_classify"]["semantics"] == "embedding_then_cluster"
    assert cfg["C8_scene_classify"]["preference"] == ["existing_scene_embedding"]
    c5 = cfg["C5_cluster_vectors"]
    assert c5["preference"] == ["existing_object_dbscan"]
    assert c5["schedule"] == "batch_rebuild"
    assert c5["invoke_on_ingest"] is False
    assert "hdbscan" not in c5["preference"]
    assert "incremental_predict_only" not in str(c5.values())


def test_skip_when_not_needed():
    policy = BrainPolicy()
    sel = policy.select(
        "C1",
        SelectionContext(photo=_photo(), capability_needed=False),
    )
    assert sel.action == "skip"


def test_reuse_when_context_says_observation_exists():
    policy = BrainPolicy()
    sel = policy.select(
        "C3",
        SelectionContext(photo=_photo(), existing_observation=True),
    )
    assert sel.action == "reuse"


def test_reuse_via_evidence_cache():
    cache = EvidenceCache()
    cache.put(
        Observation(
            photo_id="p1",
            capability_id="C3",
            provider_name="existing_region_encoder",
            payload={"dim": 384},
        )
    )
    policy = BrainPolicy(cache=cache)
    sel = policy.select("C3", SelectionContext(photo=_photo()))
    assert sel.action == "reuse"
    # Confirm hit-rate path used by callers still works
    assert cache.existing_observation("p1", "C3") is not None
    assert cache.hit_rate > 0


def test_invoke_registered_preference():
    policy = BrainPolicy()
    sel = policy.select(
        "C1",
        SelectionContext(
            photo=_photo(),
            registered_providers={"C1": ["existing_nanodet_tags", "ram_plus"]},
        ),
    )
    assert sel.action == "invoke"
    assert sel.provider_name == "existing_nanodet_tags"


def test_c2_skips_without_confidence():
    policy = BrainPolicy()
    sel = policy.select(
        "C2",
        SelectionContext(
            photo=_photo(),
            tag_confidence=0.4,
            registered_providers={"C2": ["existing_nanodet_localise"]},
        ),
    )
    assert sel.action == "skip"


def test_c2_invokes_when_conditions_met():
    policy = BrainPolicy()
    sel = policy.select(
        "C2",
        SelectionContext(
            photo=_photo(),
            tag_confidence=0.9,
            has_bbox=False,
            registered_providers={"C2": ["existing_nanodet_localise"]},
        ),
    )
    assert sel.action == "invoke"
    assert sel.provider_name == "existing_nanodet_localise"


def test_ocr_defer_when_unavailable():
    policy = BrainPolicy()
    sel = policy.select(
        "C9",
        SelectionContext(photo=_photo(), ocr_available=False),
    )
    assert sel.action == "defer"
