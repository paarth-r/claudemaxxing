import time


def compute_elapsed_percentage(resets_at, now, window_seconds=18000):
    remaining = resets_at - now
    if remaining <= 0:
        return 100.0
    if remaining >= window_seconds:
        return 0.0
    return (1 - remaining / window_seconds) * 100


def compute_ideal_rate(used_pct, remaining_seconds):
    """%/min needed from now to land at exactly 100% used right when the
    window resets - the rate that uses the whole allowance with none left over."""
    remaining_minutes = remaining_seconds / 60
    if remaining_minutes <= 0:
        return 0.0
    return max(0.0, 100.0 - used_pct) / remaining_minutes


def compute_current_rate(history, current_used_pct, now, window_start, lookback_seconds=900):
    """Recent %/min consumption rate. Prefers a trailing lookback window for
    responsiveness; falls back to the whole-window-so-far average when there
    isn't enough recent history yet for a stable reading."""
    cutoff = max(window_start, now - lookback_seconds)
    candidates = [s for s in history if s["timestamp"] >= cutoff]
    if candidates:
        earliest = min(candidates, key=lambda s: s["timestamp"])
        dt_minutes = (now - earliest["timestamp"]) / 60
        if dt_minutes >= 1:
            return (current_used_pct - earliest["used_percentage"]) / dt_minutes

    elapsed_minutes = (now - window_start) / 60
    if elapsed_minutes <= 0:
        return 0.0
    return current_used_pct / elapsed_minutes


def compute_pace(current_rate, ideal_rate, deadband_ratio=0.15, min_absolute_deadband=0.02):
    if ideal_rate <= 0:
        return "AT" if current_rate <= 0 else "ABOVE"
    deadband = max(ideal_rate * deadband_ratio, min_absolute_deadband)
    diff = current_rate - ideal_rate
    if diff > deadband:
        return "ABOVE"
    if diff < -deadband:
        return "BELOW"
    return "AT"


def is_stale(mtime, now, threshold_seconds=600):
    return (now - mtime) > threshold_seconds


def format_duration(seconds):
    if seconds <= 0:
        return "now"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return "{}h {}m".format(hours, minutes)
    return "{}m".format(minutes)


def project_landing(used_pct, current_rate, now, resets_at):
    """Where the current rate lands if it holds steady. Either the window
    exhausts (hits 100%) before it resets, or it doesn't and there's
    allowance left unused at reset time."""
    remaining_minutes = (resets_at - now) / 60
    if current_rate <= 0:
        return {"kind": "land", "pct": max(0.0, min(100.0, used_pct))}
    minutes_to_100 = (100 - used_pct) / current_rate
    if minutes_to_100 <= remaining_minutes:
        return {"kind": "exhaust", "at": now + minutes_to_100 * 60}
    pct = used_pct + current_rate * remaining_minutes
    return {"kind": "land", "pct": max(0.0, min(100.0, pct))}


def format_clock(epoch_seconds):
    return time.strftime("%-I:%M%p", time.localtime(epoch_seconds)).lower()
