import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pace import (
    compute_elapsed_percentage,
    compute_ideal_rate,
    compute_current_rate,
    compute_pace,
    is_stale,
    format_duration,
    project_landing,
    format_clock,
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

def test_project_landing_exhausts_before_reset():
    # 50% used, 1.0%/min, 60 min remaining -> exhausts at 50 min in
    result = project_landing(used_pct=50, current_rate=1.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 4000.0}

def test_project_landing_lands_after_reset():
    # 50% used, 0.5%/min, 60 min remaining -> only reaches 80% by reset
    result = project_landing(used_pct=50, current_rate=0.5, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 80.0}

def test_project_landing_zero_rate_lands_at_used_pct():
    result = project_landing(used_pct=42.0, current_rate=0.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 42.0}

def test_project_landing_negative_rate_lands_at_used_pct():
    result = project_landing(used_pct=42.0, current_rate=-0.3, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 42.0}

def test_project_landing_already_at_100_exhausts_now():
    result = project_landing(used_pct=100, current_rate=0.5, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 1000.0}

def test_project_landing_exact_boundary_is_exhaust_not_land():
    # minutes_to_100 (60) == remaining_minutes (60) exactly -> exhaust wins
    result = project_landing(used_pct=40, current_rate=1.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 4600.0}


def _local_ts(hour, minute):
    # Builds a timestamp for today at the given local hour/minute, so the
    # test is timezone-agnostic - it works no matter what TZ the machine
    # running pytest is set to.
    now = time.localtime()
    t = time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1))
    return time.mktime(t)

def test_format_clock_pm_no_leading_zero():
    assert format_clock(_local_ts(19, 20)) == "7:20pm"

def test_format_clock_am_no_leading_zero():
    assert format_clock(_local_ts(7, 5)) == "7:05am"

def test_format_clock_midnight_is_12am():
    assert format_clock(_local_ts(0, 5)) == "12:05am"

def test_format_clock_noon_is_12pm():
    assert format_clock(_local_ts(12, 0)) == "12:00pm"
