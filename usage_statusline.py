import json
import sys
import time

from state_io import (
    read_state,
    write_state,
    append_history,
    prune_history,
    WINDOW_HISTORY_PATH,
)


def build_snapshot(payload, now):
    five_hour = payload.get("rate_limits", {}).get("five_hour")
    if not five_hour:
        return None
    return {
        "timestamp": now,
        "used_percentage": five_hour["used_percentage"],
        "resets_at": five_hour["resets_at"],
    }


def format_statusline(used_percentage):
    return "5h: {}% used".format(round(used_percentage))


def merge_snapshot(existing, incoming):
    """Reconcile this session's own view with the shared state so every
    session converges on the same, most-advanced number instead of each
    showing its own possibly-lagging local cache."""
    if existing is None:
        return incoming
    if existing.get("resets_at") != incoming.get("resets_at"):
        # A new 5h window started - the incoming reading is for that window.
        return incoming
    if incoming.get("used_percentage", 0) >= existing.get("used_percentage", 0):
        return incoming
    return existing


def build_window_archive_entry(existing, final_state, now):
    """When the 5h window has just rolled over, return a permanent record of
    the just-ended window's peak usage - None if no window boundary was
    crossed. existing's used_percentage is the final peak for its window
    since merge_snapshot always keeps the running max within a window."""
    if existing is None:
        return None
    if existing.get("resets_at") == final_state.get("resets_at"):
        return None
    return {
        "resets_at": existing["resets_at"],
        "peak_usage_percentage": existing["used_percentage"],
        "archived_at": now,
    }


def main():
    try:
        payload = json.load(sys.stdin)
        now = time.time()
        incoming = build_snapshot(payload, now)
        existing = read_state()

        if incoming is None:
            # This session hasn't made its own API call yet this session -
            # still show the shared value other sessions have already learned.
            if existing is not None:
                print(format_statusline(existing["used_percentage"]))
            return

        merged = merge_snapshot(existing, incoming)
        final_state = {
            "timestamp": now,
            "used_percentage": merged["used_percentage"],
            "resets_at": merged["resets_at"],
        }

        archive_entry = build_window_archive_entry(existing, final_state, now)
        if archive_entry is not None:
            append_history(archive_entry, path=WINDOW_HISTORY_PATH)

        # Always touch state.json so its mtime proves a session is alive
        # (staleness detection), even when the value itself hasn't moved.
        write_state(final_state)

        changed = (
            existing is None
            or existing.get("used_percentage") != final_state["used_percentage"]
            or existing.get("resets_at") != final_state["resets_at"]
        )
        if changed:
            append_history(final_state)
            prune_history(now=now)

        print(format_statusline(final_state["used_percentage"]))
    except Exception:
        # Never let a statusline error break the user's Claude Code session.
        return


if __name__ == "__main__":
    main()
