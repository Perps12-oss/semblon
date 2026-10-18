"""Selection edges resize, and zoom stays on the point under the pointer."""

from semblon.focus_gesture import adjust_box, clamp_view, zoom_about


def test_right_and_bottom_edges_grow():
    assert adjust_box(10, 20, 100, 80, "r", 30, 0, 0, 0, 400, 300) == (10, 20, 130, 80)
    assert adjust_box(10, 20, 100, 80, "b", 0, 15, 0, 0, 400, 300) == (10, 20, 100, 95)


def test_left_and_top_edges_retract_from_that_side():
    assert adjust_box(10, 20, 100, 80, "l", 15, 0, 0, 0, 400, 300) == (25, 20, 85, 80)
    assert adjust_box(10, 20, 100, 80, "t", 0, 10, 0, 0, 400, 300) == (10, 30, 100, 70)


def test_corner_moves_two_edges():
    assert adjust_box(10, 20, 100, 80, "br", 12, -8, 0, 0, 400, 300) == (10, 20, 112, 72)
    assert adjust_box(10, 20, 100, 80, "tl", -5, -6, 0, 0, 400, 300) == (5, 14, 105, 86)


def test_edge_stops_at_minimum_size_and_image_bounds():
    assert adjust_box(10, 20, 100, 80, "l", 500, 0, 0, 0, 400, 300) == (102, 20, 8, 80)
    assert adjust_box(10, 20, 100, 80, "r", 500, 0, 0, 0, 150, 300) == (10, 20, 140, 80)
    assert adjust_box(10, 20, 40, 40, "t", 0, -100, 0, 5, 200, 200) == (10, 5, 40, 55)


def test_zoom_keeps_the_pointer_and_refuses_to_shrink_past_fit():
    assert zoom_about(0, 0, 1, 100, 100, 2, 200, 200) == (0.0, 0.0, 2.0)
    assert zoom_about(0, 0, 1, 0, 0, 2, 200, 200) == (100.0, 100.0, 2.0)
    assert zoom_about(0, 0, 1, 40, 40, 0.5, 200, 200) == (0.0, 0.0, 1.0)
    assert zoom_about(0, 0, 1, 40, 40, 100, 200, 200)[2] == 8.0


def test_pan_covers_the_viewport():
    assert clamp_view(40, -10, 1, 200, 100) == (0.0, 0.0, 1.0)
    assert clamp_view(1000, -1000, 2, 200, 200) == (100.0, -100.0, 2.0)
