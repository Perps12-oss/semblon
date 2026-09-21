"""Unit tests for R3 overlay scaffold + gate-aware preview helpers."""

from __future__ import annotations

import pytest

from semblon import gates
from semblon import overlay_preview as preview
from semblon import overlay_scaffold as scaffold


DISPLAY_STATES = ("unknown", "possible", "confirmed", "ruled_out", "ignored")


def test_five_display_states_have_distinct_notch_specs():
    specs = {s: scaffold.notch_spec(s) for s in DISPLAY_STATES}
    assert set(specs) == set(DISPLAY_STATES)
    fingerprints = {
        s: (spec["fill"], spec["mark"], spec["visible"]) for s, spec in specs.items()
    }
    assert len(set(fingerprints.values())) == 5


def test_five_display_states_have_distinct_border_specs():
    borders = {}
    for s in DISPLAY_STATES:
        style = scaffold.box_style(s)
        b = style["border"]
        borders[s] = (b["style"], b["dash"], b["mark"], b["visible"], style["opacity"])
    assert len(set(borders.values())) == 5


def test_box_style_composes_layers_and_notch():
    for s in DISPLAY_STATES:
        style = scaffold.box_style(s)
        assert style["display_state"] == s
        assert "outer_halo" in style["layers"]
        assert "semantic" in style["layers"]
        assert style["layers"]["outer_halo"]["width_px"] == 1.5
        assert style["layers"]["semantic"]["width_px"] == 1.5
        assert style["notch"]["fill"] == scaffold.notch_spec(s)["fill"]
        assert style["identity"]["auto_assign_person_id"] is False
        assert style["identity"]["cluster_is_person"] is False
        assert style["identity"]["conclusion"] is None


def test_visual_grammar_matches_r3_brief():
    unknown = scaffold.box_style("unknown")
    assert unknown["border"]["style"] == "dashed"
    assert unknown["border"]["dash"] == (6, 4)
    assert unknown["notch"]["fill"] == "empty_outline"

    possible = scaffold.box_style("possible")
    assert possible["border"]["style"] == "dashed"
    assert possible["border"]["dash"] == (3, 2)
    assert possible["notch"]["fill"] == "half_filled"

    confirmed = scaffold.box_style("confirmed")
    assert confirmed["border"]["style"] == "solid"
    assert confirmed["border"]["dash"] is None
    assert confirmed["notch"]["fill"] == "solid"

    ruled = scaffold.box_style("ruled_out")
    assert ruled["border"]["style"] == "dashed"
    assert ruled["border"]["dash"] == (6, 4)
    assert ruled["border"]["mark"] == "≠"
    assert ruled["notch"]["fill"] == "empty_outline"
    assert ruled["notch"]["mark"] == "slash"

    ignored = scaffold.box_style("ignored")
    assert ignored["border"]["style"] == "none"
    assert ignored["border"]["visible"] is False
    assert ignored["notch"]["visible"] is False
    assert ignored["opacity"] == pytest.approx(0.35)


def test_stroke_layers_inverse_luminance():
    dark = scaffold.stroke_layers(0.1, "unknown")
    light = scaffold.stroke_layers(0.9, "unknown")
    # Dark crop → lighter halo; light crop → darker halo.
    dark_level = int(dark["outer_halo"]["color"][1:3], 16)
    light_level = int(light["outer_halo"]["color"][1:3], 16)
    assert dark_level > light_level
    assert dark["semantic"]["color"] == light["semantic"]["color"]


def test_stroke_layers_ignored_hides_strokes():
    layers = scaffold.stroke_layers(0.5, "ignored")
    assert layers["outer_halo"]["visible"] is False
    assert layers["semantic"]["visible"] is False
    assert layers["opacity"] == pytest.approx(0.35)


def test_normalize_rejects_unknown_state():
    with pytest.raises(ValueError, match="unknown display_state"):
        scaffold.normalize_display_state("candidate")


def test_preview_noop_when_gate_off(monkeypatch):
    monkeypatch.setenv("SEMBLON_GATE_LIVE_OVERLAY", "0")
    assert preview.render_overlay_enabled() is False
    boxes = [{"id": "f1", "display_state": "possible", "bbox": [0, 0, 1, 1]}]
    out = preview.apply_overlay_styles(boxes)
    assert len(out) == 1
    assert "overlay_style" not in out[0]
    canvas_out = preview.apply_to_canvas(boxes)
    assert "overlay_style" not in canvas_out[0]


def test_preview_require_enabled_raises_when_off(monkeypatch):
    monkeypatch.setenv("SEMBLON_GATE_LIVE_OVERLAY", "0")
    with pytest.raises(RuntimeError, match="is OFF"):
        preview.require_overlay_enabled()
    with pytest.raises(RuntimeError, match="is OFF"):
        preview.build_styled_boxes([{"id": "f1", "display_state": "unknown"}])


def test_preview_applies_styles_when_gate_on(monkeypatch):
    monkeypatch.delenv("SEMBLON_GATE_LIVE_OVERLAY", raising=False)
    assert preview.render_overlay_enabled() is True
    boxes = [
        {"id": "f1", "display_state": "confirmed", "bbox": [0, 0, 10, 10]},
        {"id": "f2", "display_state": "ruled_out"},
    ]
    out = preview.apply_overlay_styles(boxes)
    assert out[0]["overlay_style"]["display_state"] == "confirmed"
    assert out[1]["overlay_style"]["border"]["mark"] == "≠"
    assert all(b["overlay_style"]["identity"]["conclusion"] is None for b in out)

    custom = {"f1": scaffold.box_style("ignored")}
    mapped = preview.apply_overlay_styles(boxes, custom)
    assert mapped[0]["overlay_style"]["display_state"] == "ignored"
    assert mapped[1]["overlay_style"]["display_state"] == "ruled_out"

    built = preview.build_styled_boxes(boxes)
    assert built[0]["overlay_style"]["notch"]["fill"] == "solid"


def test_no_fake_identity_in_gate_status():
    report = gates.status_report(keys=["live_overlay"])
    gate = report["gates"][0]
    assert gate["key"] == "live_overlay"
    assert gate["default"] is True
    assert "identity" in gate["human_verify"].lower() or "notch" in gate["human_verify"].lower()
