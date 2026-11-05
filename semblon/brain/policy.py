"""BrainPolicy — declarative select: reuse | invoke | skip | defer.

Loads docs/brain/policy.yaml without a PyYAML dependency (controlled subset).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from semblon.brain.cache import EvidenceCache
from semblon.brain.observation import PhotoRef

Action = Literal["reuse", "invoke", "skip", "defer"]

CAPABILITY_KEYS = {
    "C1": "C1_tag_generic",
    "C2": "C2_localise_object",
    "C3": "C3_embed_object",
    "C4": "C4_embed_face",
    "C5": "C5_cluster_vectors",
    "C6": "C6_search_similar",
    "C7": "C7_verify_same_instance",
    "C8": "C8_scene_classify",
    "C9": "C9_ocr",
}


@dataclass(frozen=True)
class Selection:
    action: Action
    provider_name: str | None = None
    reason: str | None = None


@dataclass
class SelectionContext:
    photo: PhotoRef
    capability_needed: bool = True
    existing_observation: bool = False
    tag_confidence: float | None = None
    has_bbox: bool = False
    ocr_available: bool | None = None
    hardware_ceiling: str = "standard"
    adopted_providers: dict[str, list[str]] = field(default_factory=dict)
    registered_providers: dict[str, list[str]] = field(default_factory=dict)


def default_policy_path() -> Path:
    here = Path(__file__).resolve()
    repo = here.parents[2] / "docs" / "brain" / "policy.yaml"
    if repo.is_file():
        return repo
    bundled = here.parent / "policy.yaml"
    return bundled


def load_policy_yaml(path: Path | None = None) -> dict[str, Any]:
    target = path or default_policy_path()
    text = target.read_text(encoding="utf-8")
    return _parse_simple_yaml(text)


class BrainPolicy:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        cache: EvidenceCache | None = None,
    ) -> None:
        self._config = config if config is not None else load_policy_yaml()
        self._cache = cache

    def select(self, capability_id: str, context: SelectionContext) -> Selection:
        if capability_id not in CAPABILITY_KEYS:
            return Selection("defer", reason=f"unknown capability {capability_id}")

        if not context.capability_needed:
            return Selection("skip", reason="capability not needed")

        if capability_id == "C9" and context.ocr_available is False:
            return Selection("defer", reason="ocr unavailable")

        key = CAPABILITY_KEYS[capability_id]
        rule = self._config.get(key) or {}

        if self._should_reuse(capability_id, context, rule):
            return Selection("reuse", reason="observation_exists")

        if capability_id == "C2" and not self._c2_invoke_ok(context, rule):
            return Selection("skip", reason="invoke_only_if not met")

        provider = self._pick_provider(capability_id, rule, context)
        if provider is None:
            return Selection("defer", reason="no registered provider")
        return Selection("invoke", provider_name=provider, reason="policy select")

    def _should_reuse(
        self,
        capability_id: str,
        context: SelectionContext,
        rule: dict[str, Any],
    ) -> bool:
        if context.existing_observation:
            return True
        if rule.get("skip_if") == "observation_exists" and self._cache is not None:
            return self._cache.has_observation(
                context.photo.photo_id,
                capability_id,
                None,
            )
        return False

    def _c2_invoke_ok(self, context: SelectionContext, rule: dict[str, Any]) -> bool:
        conditions = rule.get("invoke_only_if") or []
        if not conditions:
            return True
        if "tag_confidence_ge_0_75" in conditions:
            if context.tag_confidence is None or context.tag_confidence < 0.75:
                return False
        if "no_existing_bbox" in conditions and context.has_bbox:
            return False
        return True

    def _pick_provider(
        self,
        capability_id: str,
        rule: dict[str, Any],
        context: SelectionContext,
    ) -> str | None:
        preference = list(rule.get("preference") or [])
        adopted = context.adopted_providers.get(capability_id) or []
        registered = context.registered_providers.get(capability_id) or []
        for name in preference:
            if name in adopted:
                return name
        # Inc 1: nothing adopted — first registered preference is selectable
        # for arbitration tests; callers must not load models from this alone.
        for name in preference:
            if name in registered:
                return name
        if preference and not registered and not adopted:
            return str(preference[0])
        return None


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Minimal indentation YAML for Brain policy files. Not a general parser."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        code = lines[i].split("#", 1)[0]
        if not code.strip():
            i += 1
            continue
        indent = len(code) - len(code.lstrip(" "))
        line = code.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"list item without list parent: {line}")
            parent.append(_scalar(line[2:].strip()))
            i += 1
            continue

        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"mapping under non-dict: {line}")

        if rest != "":
            parent[key] = _scalar(rest)
            i += 1
            continue

        j = i + 1
        while j < len(lines) and not lines[j].split("#", 1)[0].strip():
            j += 1
        if j < len(lines):
            peek = lines[j].split("#", 1)[0]
            peek_indent = len(peek) - len(peek.lstrip(" "))
            peek_line = peek.strip()
            if peek_indent > indent and peek_line.startswith("- "):
                lst: list[Any] = []
                parent[key] = lst
                stack.append((indent, lst))
                i += 1
                continue

        child: dict[str, Any] = {}
        parent[key] = child
        stack.append((indent, child))
        i += 1
    return root


def _scalar(raw: str) -> Any:
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1].strip()
        out: dict[str, Any] = {}
        if not inner:
            return out
        for part in inner.split(","):
            k, _, v = part.partition(":")
            out[k.strip()] = _scalar(v.strip())
        return out
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    low = raw.lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"null", "none", "~"}:
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw
