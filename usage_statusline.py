import json
import sys
import time

from state_io import read_state, write_state, append_history, prune_history

MIN_PERSIST_INTERVAL_SECONDS = 15


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


def main():
    try:
        payload = json.load(sys.stdin)
        now = time.time()
        snapshot = build_snapshot(payload, now)
        if snapshot is None:
            return

        # Claude Code can invoke this many times per second; the underlying
        # rate-limit percentage can jitter on concurrent in-flight requests.
        # Persist at most once per MIN_PERSIST_INTERVAL_SECONDS so history.jsonl
        # stays a meaningful trend instead of sub-second noise, while still
        # printing the freshest known value to the visible statusline.
        existing = read_state()
        should_persist = (
            existing is None
            or (now - existing.get("timestamp", 0)) >= MIN_PERSIST_INTERVAL_SECONDS
        )
        if should_persist:
            write_state(snapshot)
            append_history(snapshot)
            prune_history(now=now)

        print(format_statusline(snapshot["used_percentage"]))
    except Exception:
        # Never let a statusline error break the user's Claude Code session.
        return


if __name__ == "__main__":
    main()
