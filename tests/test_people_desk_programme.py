"""People desk programme items — tracks honesty (cluster ≠ person; track ≠ person)."""

from __future__ import annotations

from semblon.native_shell.presentation import group_band_label, group_list_title


def test_track_titles_are_not_people():
    assert group_list_title(named=False, names=[], kind="track", band="track") == "Track (not a person)"
    assert "not a person" in group_band_label(named=False, kind="track", band="track").lower()


def test_candidate_titles_unchanged():
    assert group_list_title(named=False, names=[], kind="cluster", band="strong") == "Strong candidate group"
    assert group_list_title(named=True, names=["Ada"], kind="cluster", band="strong") == "Ada"
