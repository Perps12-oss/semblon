"""Internal GUI feature registry — not a plugin host.

Features register navigation, routes, and commands. The Tk Home shell
loops the registry for sidebar / palette / overflow / inspector surfaces.
CapabilitySpec (runtime_contract) and GUI_PATHS (product_exposure) stay
separate: models catalog and exposure classification, not page lists.

No user-installable plugins. No schema change. Identity stays FaceKit-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

__all__ = [
    "DuplicateFeatureId",
    "Feature",
    "FeatureRegistry",
    "GuiCommand",
    "NavContribution",
    "UnknownFeature",
    "default_registry",
    "reset_default_registry_for_tests",
]

Surface = str  # "nav" | "palette" | "overflow" | "inspector" | "context"


class DuplicateFeatureId(ValueError):
    """Raised when register() sees an id already present."""


class UnknownFeature(KeyError):
    """Raised when get() cannot find a feature id."""


@dataclass(frozen=True)
class NavContribution:
    """Sidebar (and palette Go-to) contribution for one destination."""

    section: str
    route_id: str
    label: str
    shortcut: str | None = None
    order: int = 0


@dataclass(frozen=True)
class GuiCommand:
    """One user action, reusable across inspector / palette / overflow / context."""

    id: str
    label: str
    run: Callable[..., Any]
    surfaces: frozenset[str] = field(default_factory=lambda: frozenset({"palette"}))
    available: Callable[..., bool] | None = None
    reason: Callable[..., str] | None = None
    requires_context: bool = False

    def is_available(self, host: Any = None, context: Any = None) -> bool:
        if self.available is None:
            return True
        try:
            return bool(self.available(host, context))
        except TypeError:
            return bool(self.available(host))

    def disable_reason(self, host: Any = None, context: Any = None) -> str:
        if self.reason is None:
            return ""
        try:
            return str(self.reason(host, context) or "")
        except TypeError:
            return str(self.reason(host) or "")

    def execute(self, host: Any = None, context: Any = None) -> Any:
        try:
            return self.run(host, context)
        except TypeError:
            return self.run(host)


@dataclass(frozen=True)
class Feature:
    """Product area: optional nav + route page + commands."""

    id: str
    label: str
    nav: NavContribution | None = None
    route_id: str | None = None
    page: Callable[..., Any] | None = None
    available: Callable[..., bool] | None = None
    commands: tuple[GuiCommand, ...] = ()

    def resolved_route_id(self) -> str | None:
        if self.route_id:
            return self.route_id
        if self.nav is not None:
            return self.nav.route_id
        return None

    def is_available(self, host: Any = None) -> bool:
        if self.available is None:
            return True
        return bool(self.available(host))


class FeatureRegistry:
    """In-process registry. Not persisted. Not a plugin loader."""

    def __init__(self) -> None:
        self._by_id: dict[str, Feature] = {}
        self._order: list[str] = []

    def register(self, feature: Feature) -> None:
        if feature.id in self._by_id:
            raise DuplicateFeatureId(f"feature already registered: {feature.id!r}")
        self._by_id[feature.id] = feature
        self._order.append(feature.id)

    def get(self, feature_id: str) -> Feature:
        try:
            return self._by_id[feature_id]
        except KeyError as e:
            raise UnknownFeature(feature_id) from e

    def __contains__(self, feature_id: object) -> bool:
        return isinstance(feature_id, str) and feature_id in self._by_id

    def features(self, *, host: Any = None, available_only: bool = False) -> list[Feature]:
        out: list[Feature] = []
        for fid in self._order:
            feat = self._by_id[fid]
            if available_only and not feat.is_available(host):
                continue
            out.append(feat)
        return out

    def feature_for_route(self, route_id: str) -> Feature | None:
        for feat in self.features():
            if feat.resolved_route_id() == route_id:
                return feat
        return None

    def resolve_route(self, route_id: str) -> Callable[..., Any] | None:
        feat = self.feature_for_route(route_id)
        if feat is None or feat.page is None:
            return None
        return feat.page

    def nav_contributions(self, *, host: Any = None) -> list[NavContribution]:
        rows: list[NavContribution] = []
        for feat in self.features(host=host, available_only=True):
            if feat.nav is None:
                continue
            rows.append(feat.nav)
        # Preserve registration order within each section; section order is fixed.
        return rows

    _SECTION_ORDER = ("ASK", "LIBRARY", "PEOPLE", "ACTIVITY")

    def nav_sections(
        self, *, host: Any = None
    ) -> list[tuple[str, list[NavContribution]]]:
        """Grouped like today's HOME_NAV: (section, items)."""
        buckets: dict[str, list[NavContribution]] = {}
        for nav in self.nav_contributions(host=host):
            buckets.setdefault(nav.section, []).append(nav)
        for items in buckets.values():
            items.sort(key=lambda n: (n.order, n.route_id))
        out: list[tuple[str, list[NavContribution]]] = []
        seen: set[str] = set()
        for sec in self._SECTION_ORDER:
            if sec in buckets:
                out.append((sec, buckets[sec]))
                seen.add(sec)
        for sec, items in buckets.items():
            if sec not in seen:
                out.append((sec, items))
        return out

    def home_nav_tuple(
        self, *, host: Any = None
    ) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
        """Compatibility shape matching historical HOME_NAV."""
        return tuple(
            (section, tuple((n.route_id, n.label) for n in items))
            for section, items in self.nav_sections(host=host)
        )

    def commands(
        self,
        *,
        surface: str | None = None,
        host: Any = None,
        context: Any = None,
        available_only: bool = False,
    ) -> list[GuiCommand]:
        out: list[GuiCommand] = []
        seen: set[str] = set()
        for feat in self.features(host=host, available_only=True):
            for cmd in feat.commands:
                if cmd.id in seen:
                    continue
                if surface is not None and surface not in cmd.surfaces:
                    continue
                if available_only and not cmd.is_available(host, context):
                    continue
                seen.add(cmd.id)
                out.append(cmd)
        return out

    def get_command(self, command_id: str) -> GuiCommand | None:
        for feat in self.features():
            for cmd in feat.commands:
                if cmd.id == command_id:
                    return cmd
        return None


_DEFAULT: FeatureRegistry | None = None


def default_registry() -> FeatureRegistry:
    """Process-wide product registry (lazy)."""
    global _DEFAULT
    if _DEFAULT is None:
        from semblon.product_features import build_product_registry

        _DEFAULT = build_product_registry()
    return _DEFAULT


def reset_default_registry_for_tests(registry: FeatureRegistry | None = None) -> FeatureRegistry:
    """Tests only: replace or clear the process default."""
    global _DEFAULT
    if registry is None:
        from semblon.product_features import build_product_registry

        registry = build_product_registry()
    _DEFAULT = registry
    return _DEFAULT
