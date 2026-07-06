import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from heatmap import color_for_pct, format_time_ago, build_cube_row

def test_color_for_pct_zero_is_pure_grey():
    assert color_for_pct(0) == "#{:02x}{:02x}{:02x}".format(*color_for_pct.GREY)

def test_color_for_pct_hundred_is_pure_green():
    assert color_for_pct(100) == "#{:02x}{:02x}{:02x}".format(*color_for_pct.GREEN)

def test_color_for_pct_clamps_out_of_range():
    assert color_for_pct(150) == color_for_pct(100)
    assert color_for_pct(-10) == color_for_pct(0)

def test_color_for_pct_midpoint_is_between_grey_and_green():
    mid = color_for_pct(50)
    assert mid != color_for_pct(0)
    assert mid != color_for_pct(100)

def test_format_time_ago_now():
    assert format_time_ago(30) == "now"

def test_format_time_ago_minutes():
    assert format_time_ago(600) == "10m"

def test_format_time_ago_hours():
    assert format_time_ago(7200) == "2h"

def test_format_time_ago_days():
    assert format_time_ago(86400 * 3) == "3d"

def test_build_cube_row_includes_current_window_last():
    window_history = [
        {"resets_at": 100, "peak_usage_percentage": 50},
        {"resets_at": 200, "peak_usage_percentage": 80},
    ]
    cubes = build_cube_row(window_history, current_peak_pct=15, current_window_end=300, now=250)
    assert len(cubes) == 3
    assert cubes[-1]["pct"] == 15
    assert cubes[-1]["ago_seconds"] == 0  # in-progress window reads as "now"

def test_build_cube_row_caps_to_max_cubes():
    window_history = [{"resets_at": i * 100, "peak_usage_percentage": i} for i in range(30)]
    cubes = build_cube_row(window_history, current_peak_pct=0, current_window_end=3100, now=3050, max_cubes=10)
    assert len(cubes) == 10
    # most recent completed windows should be the ones kept (plus current)
    assert cubes[-2]["pct"] == 29

def test_build_cube_row_no_usage_gives_zero_pct():
    cubes = build_cube_row([], current_peak_pct=0, current_window_end=100, now=50)
    assert cubes[0]["pct"] == 0
