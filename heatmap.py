GREY = (90, 90, 90)
GREEN = (57, 211, 83)

CUBE_WIDTH = 4
GAP_WIDTH = 1  # a quarter of a cube


def color_for_pct(pct):
    pct = max(0, min(100, pct))
    t = pct / 100
    r = round(GREY[0] + (GREEN[0] - GREY[0]) * t)
    g = round(GREY[1] + (GREEN[1] - GREY[1]) * t)
    b = round(GREY[2] + (GREEN[2] - GREY[2]) * t)
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


color_for_pct.GREY = GREY
color_for_pct.GREEN = GREEN


def format_time_ago(seconds_ago):
    if seconds_ago < 300:
        return "now"
    if seconds_ago < 3600:
        return "{}m".format(int(seconds_ago // 60))
    if seconds_ago < 86400:
        return "{}h".format(int(seconds_ago // 3600))
    return "{}d".format(int(seconds_ago // 86400))


def build_cube_row(window_history, current_peak_pct, current_window_end, now, max_cubes=20):
    """Chronological list of completed windows plus the in-progress current
    window as the last (rightmost) cube. Each entry: {"pct", "ago_seconds"}."""
    entries = sorted(window_history, key=lambda e: e["resets_at"])
    entries = entries + [
        {"resets_at": current_window_end, "peak_usage_percentage": current_peak_pct}
    ]
    entries = entries[-max_cubes:]

    return [
        {
            "pct": e.get("peak_usage_percentage", 0),
            "ago_seconds": max(0, now - e["resets_at"]),
        }
        for e in entries
    ]
