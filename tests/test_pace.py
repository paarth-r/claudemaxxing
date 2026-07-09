import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pace import (
    compute_elapsed_percentage,
    compute_ideal_rate,
    compute_current_rate,
    compute_pace,
    is_stale,
    format_duration,
)

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

def test_compute_ideal_rate_basic():
    # 50% remaining, 60 minutes left -> 0.8333%/min to land at exactly 100%
    assert round(compute_ideal_rate(used_pct=50, remaining_seconds=3600), 4) == 0.8333

def test_compute_ideal_rate_no_time_remaining_is_zero():
    assert compute_ideal_rate(used_pct=50, remaining_seconds=0) == 0.0
    assert compute_ideal_rate(used_pct=50, remaining_seconds=-10) == 0.0

def test_compute_ideal_rate_already_at_100_is_zero():
    assert compute_ideal_rate(used_pct=100, remaining_seconds=3600) == 0.0

def test_compute_current_rate_uses_recent_trailing_window():
    now = 10000
    window_start = 0
    history = [
        {"timestamp": now - 600, "used_percentage": 10},  # 10 min ago
        {"timestamp": now - 60, "used_percentage": 16},
    ]
    # earliest sample within lookback is 10 min ago at 10%; now at 20% -> 1%/min
    rate = compute_current_rate(history, current_used_pct=20, now=now, window_start=window_start, lookback_seconds=900)
    assert round(rate, 4) == 1.0

def test_compute_current_rate_falls_back_to_whole_window_average_when_sparse():
    now = 10000
    window_start = now - 2000  # 2000s = ~33.3 min into the window
    history = []  # no samples at all yet
    rate = compute_current_rate(history, current_used_pct=10, now=now, window_start=window_start)
    assert round(rate, 4) == round(10 / (2000 / 60), 4)

def test_compute_current_rate_zero_elapsed_is_zero():
    now = 1000
    rate = compute_current_rate([], current_used_pct=0, now=now, window_start=now)
    assert rate == 0.0

def test_compute_pace_above_when_current_exceeds_ideal():
    assert compute_pace(current_rate=1.0, ideal_rate=0.5) == "ABOVE"

def test_compute_pace_below_when_current_under_ideal():
    assert compute_pace(current_rate=0.1, ideal_rate=0.5) == "BELOW"

def test_compute_pace_at_within_deadband():
    assert compute_pace(current_rate=0.52, ideal_rate=0.5) == "AT"
    assert compute_pace(current_rate=0.48, ideal_rate=0.5) == "AT"

def test_compute_pace_ideal_zero_and_still_using_is_above():
    assert compute_pace(current_rate=0.1, ideal_rate=0.0) == "ABOVE"

def test_compute_pace_ideal_zero_and_idle_is_at():
    assert compute_pace(current_rate=0.0, ideal_rate=0.0) == "AT"

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
