# GUI registry implementation

**Date:** 2026-09-28  
**Slice:** internal feature registry for Tk Home (`semblon home`).  
**Authority:** research in PR #110 (`docs/GUI-*-*.md`); north star remains `docs/SEM-ARCH-V1.4.md`.  
**Non-goals:** no GUI visual redesign, no framework change, no plugin host, no schema/DDL, no identity-threshold change.

Windows Tk live launch was **not** exercised in this environment. Portable pytest covers the registry and source-shape regressions.

---

## What was introduced

| Piece | Path | Role |
|---|---|---|
| `Feature`, `GuiCommand`, `NavContribution`, `FeatureRegistry` | `semblon/gui_registry.py` | Registration, lookup, nav grouping, route resolve, command discovery, availability |
| Product seed | `semblon/product_features.py` | Registers today’s destinations + Phase 7 commands |
| Activity page module | `semblon/features/activity_feature.py` | First migrated production feature |
| Demo registration helper | `register_demo_feature()` in `product_features.py` | Architectural acceptance (tests only) |
| Tests | `tests/test_gui_registry.py` (+ Activity assert update) | Registry + shell consumption + demo |

`CapabilitySpec` / `GUI_PATHS` are unchanged: model catalog and exposure classification, **not** the UI registry.

---

## What was migrated

- **Sidebar** builds from `registry.nav_sections()` (same labels/order as former `HOME_NAV`).
- **`HOME_NAV`** is derived from the registry (`refresh_home_nav()`).
- **`_navigate`** resolves `registry.resolve_route(route_id)` first; keeps a compatibility fallback.
- **Ctrl+1…5** bind from nav `shortcut` metadata.
- **More (overflow)** rebuilt from `commands(surface="overflow")`.
- **Ctrl+K** lists nav destinations + Settings + palette commands (with type-to-filter).
- **Inspector** packs registry contextual commands (`person.history`, `person.identify_face`, …) beside existing verbs; enablement synced on selection.
- **Activity** page/build/refresh live in `features/activity_feature.py`; `HomeApp` keeps thin wrappers.

---

## What remains hard-coded

- Job chrome (folder / Pause / Cancel / progress / Watchdog).
- Landing / processing / result-card state machine on route `home`.
- Inspector **identity verbs** (Name / Assign / Merge / Split / Rule out / Ignore) still use `inspector_verbs.py` widgets constructed in `HomeApp.__init__` (command *records* exist for Lens/person extras; verb buttons are not yet pure command renderers).
- Settings panel body builder.
- Review Toplevel, Live overlay entry (also registered as overflow commands that call the same methods).
- `lens_home.install` mouse-up monkeypatch (unchanged).
- Optional Qt `semblon shell` nav (not retargeted in this slice).

---

## Where new features register

```python
from semblon.gui_registry import Feature, GuiCommand, NavContribution, default_registry
# Prefer: add to semblon/product_features.py::build_product_registry()
# or register onto a registry passed into tests via reset_default_registry_for_tests.
```

### Example — new page (sidebar destination)

```python
reg.register(
    Feature(
        id="notes",
        label="Notes",
        nav=NavContribution(section="ACTIVITY", route_id="notes", label="Notes", order=1),
        route_id="notes",
        page=lambda host: host._set_inspector("Notes", ["…"]),
    )
)
```

No edits to `HOME_NAV`, `_navigate` if/elif, More, or Ctrl+K implementation are required once the feature is registered before Home launches (product seed or test registry reset).

### Example — new command (no nav)

```python
GuiCommand(
    id="person.history",
    label="Show history",
    run=my_run,
    surfaces=frozenset({"inspector", "palette", "context"}),
    available=lambda host, ctx: …,
    requires_context=True,
)
```

Attach on an existing `Feature.commands` tuple in `product_features.py`.

### Architectural acceptance

`register_demo_feature(reg)` proves a feature becomes discoverable (nav + route + palette/overflow/inspector command) **without** the string `registry_demo` appearing in `HomeApp` source.

---

## Phase 7 exposures (existing engines only)

| Capability | Command / route | Notes |
|---|---|---|
| Photos grid | `library.browse_photos` → route `photos` | Overflow / palette |
| Person history | `person.history` | Inspector / palette when one person selected |
| Identify named match | `person.identify_face` | `identify_face(..., record=False)` |
| OCR/text search affordance | `lens.search_text` | Focuses search; explains OCR fallback |
| Lens region / similar / ask | `lens.select_region`, `lens.find_similar`, `lens.ask` | Distinct commands — not one vague Lens action |
| Library backup | `library.backup` | `store.backup_store` |
| Folder update | `library.watch_folder` | JobEngine scan; continuous `semblon watch` remains CLI |
| Person-folder export | `library.export_person_folders` | `export_views` |

Not registered: eval, observatory, probes, lab diagnostics.

---

## Known limitations

- Circular-safe: page factories import `home_ui` helpers lazily.
- Overflow/palette may list several library commands; labels are deduped.
- Continuous folder **watch** is not a background GUI daemon — ingest scan + CLI note.
- Identify / history need a real selection context; without Tk they are unit-tested as registration only.
- Demo feature is **not** in the default product registry (tests only).

---

## Remaining migration work

1. Render inspector identity verbs purely from command records (`inspector_verbs` → `GuiCommand`).
2. Drop `_navigate` fallback once all routes only use registry pages.
3. Settings sections as contributions.
4. Remove `lens_home.install` monkeypatch; call `lens.find_similar` explicitly (research Step 5).
5. Optional: Qt shell reads the same nav contributions.
6. Photos IA fix (dashboard vs grid label) — separate visual/IA slice.

---

## Coupling report

### Shell modifications required to add a new feature **BEFORE** this change

Edit all of: `HOME_NAV`, `_navigate()` if/elif, More menu literals, Ctrl+K destination list, often inspector button construction, plus any Activity-style methods on `HomeApp`.

### Shell modifications required **AFTER** this change

Register a `Feature` / `GuiCommand` in `semblon/product_features.py` (or `registry.register(...)` before launch).  
**Do not** edit `HomeApp`, `HOME_NAV`, `_navigate`, More, Ctrl+K, or inspector packing for a normal new destination or contextual command.

Evidence: `tests/test_gui_registry.py::test_demo_feature_registers_without_editing_homeapp`.
