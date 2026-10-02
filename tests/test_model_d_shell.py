"""Model D — Memory-first Stage dissolve shell contracts."""

from __future__ import annotations

import inspect

from semblon.fluid_shell import (
    STAGE_CTA,
    STAGE_DISCOVER_TITLE,
    STAGE_EXPLORE_TITLE,
    STAGE_HEADLINE,
    STAGE_PEOPLE_TITLE,
)
from semblon.home_ui import HomeApp


def test_stage_copy_is_capability_not_face_first():
    assert "memory" in STAGE_HEADLINE.lower()
    assert STAGE_EXPLORE_TITLE == "Explore"
    assert STAGE_DISCOVER_TITLE == "Discover"
    assert STAGE_PEOPLE_TITLE == "People"
    assert "folder" in STAGE_CTA.lower()
    assert "scan faces" not in STAGE_CTA.lower()
    assert "face recognition" not in STAGE_HEADLINE.lower()


def test_home_app_has_no_main_sidebar_scaffold():
    init = inspect.getsource(HomeApp.__init__)
    assert "_sidebar = None" in init
    assert "btn_discover" in init
    assert "btn_brand" in init
    assert "pack(side=tk.LEFT, fill=tk.Y)" not in init or "_sidebar = None" in init
    # No permanent destination rail construction.
    assert "for section, items in self._registry.nav_sections()" not in init


def test_stage_dissolve_helpers_exist():
    src = inspect.getsource(HomeApp)
    assert "_show_stage" in src
    assert "_dissolve_to_memory" in src
    assert "_open_home_stage" in src
    assert "_sync_activity_chrome" in src
    stage = inspect.getsource(HomeApp._show_stage)
    assert "StageCapabilityCard" in stage
    assert "STAGE_EXPLORE_TITLE" in stage
    assert "STAGE_DISCOVER_TITLE" in stage
    assert "STAGE_PEOPLE_TITLE" in stage
    assert "STAGE_ACTIVITY" not in stage
    dissolve = inspect.getsource(HomeApp._dissolve_to_memory)
    assert "dissolve_stage" in dissolve
