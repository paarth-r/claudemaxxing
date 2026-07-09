def compute_elapsed_percentage(resets_at, now, window_seconds=18000):
    remaining = resets_at - now
    if remaining <= 0:
        return 100.0
    if remaining >= window_seconds:
        return 0.0
    return (1 - remaining / window_seconds) * 100


def compute_pace(used_pct, elapsed_pct, deadband=3.0):
    diff = used_pct - elapsed_pct
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
