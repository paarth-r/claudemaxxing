import json
import sys
import time

from state_io import write_state, append_history, prune_history


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
    return "5h: {}% used".format(used_percentage)


def main():
    try:
        payload = json.load(sys.stdin)
        now = time.time()
        snapshot = build_snapshot(payload, now)
        if snapshot is None:
            return
        write_state(snapshot)
        append_history(snapshot)
        prune_history(now=now)
        print(format_statusline(snapshot["used_percentage"]))
    except Exception:
        # Never let a statusline error break the user's Claude Code session.
        return


if __name__ == "__main__":
    main()
