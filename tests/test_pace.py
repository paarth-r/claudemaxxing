import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pace import compute_elapsed_percentage, compute_pace, is_stale, format_duration

def test_elapsed_percentage_at_window_start():
    now = 1000
    resets_at = now + 18000
    assert compute_elapsed_percentage(resets_at, now) == 0.0

def test_elapsed_percentage_halfway():
    now = 1000
    resets_at = now + 9000
    assert compute_elapsed_percentage(resets_at, now) == 50.0

def test_elapsed_percentage_past_reset_clamps_to_100():
    now = 1000
    resets_at = now - 5
    assert compute_elapsed_percentage(resets_at, now) == 100.0

def test_pace_above():
    assert compute_pace(used_pct=60, elapsed_pct=50) == "ABOVE"

def test_pace_below():
    assert compute_pace(used_pct=40, elapsed_pct=50) == "BELOW"

def test_pace_at_within_deadband():
    assert compute_pace(used_pct=51, elapsed_pct=50) == "AT"
    assert compute_pace(used_pct=48, elapsed_pct=50) == "AT"

def test_is_stale():
    now = 10000
    assert is_stale(mtime=now - 601, now=now) is True
    assert is_stale(mtime=now - 599, now=now) is False

def test_format_duration_hours_and_minutes():
    assert format_duration(2 * 3600 + 43 * 60) == "2h 43m"

def test_format_duration_minutes_only():
    assert format_duration(9 * 60) == "9m"

def test_format_duration_zero_or_negative_is_now():
    assert format_duration(0) == "now"
    assert format_duration(-30) == "now"

def test_format_duration_rounds_down_seconds():
    assert format_duration(125) == "2m"
