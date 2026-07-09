import os
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from state_io import read_state, read_history, STATE_PATH, WINDOW_HISTORY_PATH
from pace import compute_elapsed_percentage, compute_pace, is_stale, format_duration
from quotes import BELOW_QUOTES, AT_QUOTES, ABOVE_QUOTES, pick_quote

QUOTE_POOLS = {"BELOW": BELOW_QUOTES, "AT": AT_QUOTES, "ABOVE": ABOVE_QUOTES}
from stats import tokens_per_minute, count_active_claude_sessions
from heatmap import build_cube_row, color_for_pct, format_time_ago, CUBE_WIDTH, GAP_WIDTH

POLL_SECONDS = 60
SPARK_CHARS = "▁▂▃▄▅▆▇█"
BAR_WIDTH = 60

console = Console()


def sparkline(values):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    return "".join(
        SPARK_CHARS[min(int((v - lo) / span * (len(SPARK_CHARS) - 1)), len(SPARK_CHARS) - 1)]
        for v in values
    )


def bar(pct, width=BAR_WIDTH):
    pct = max(0, min(100, pct))
    filled = int(round(pct / 100 * width))
    return ("█" * filled) + ("░" * (width - filled))


def pace_color(pace):
    return {"ABOVE": "red", "AT": "yellow", "BELOW": "green"}[pace]


def render_heatmap(window_history, current_peak_pct, current_window_end, now):
    cubes = build_cube_row(window_history, current_peak_pct, current_window_end, now)
    if not cubes:
        return None

    cube_line = Text()
    for i, cube in enumerate(cubes):
        cube_line.append(" " * CUBE_WIDTH, style="on {}".format(color_for_pct(cube["pct"])))
        if i < len(cubes) - 1:
            cube_line.append(" " * GAP_WIDTH)

    total_width = len(cubes) * CUBE_WIDTH + (len(cubes) - 1) * GAP_WIDTH
    if len(cubes) <= 1:
        # No completed 5h window yet - nothing meaningful to date-range.
        timeline = Text("history builds up as 5h windows complete", style="dim")
    else:
        left_label = "{} ago".format(format_time_ago(cubes[0]["ago_seconds"]))
        right_label = "now"
        padding = max(1, total_width - len(left_label) - len(right_label))
        timeline = Text(left_label + " " * padding + right_label, style="dim")

    return cube_line, timeline


def render(state, history, last_quote, live_stats=None, window_history=None):
    if state is None:
        return Panel(Text("Waiting for first Claude Code render...", style="dim"),
                      title="claudemaxxing", height=console.height)

    used_pct = state["used_percentage"]
    resets_at = state["resets_at"]
    now = time.time()
    elapsed_pct = compute_elapsed_percentage(resets_at, now)
    pace = compute_pace(used_pct, elapsed_pct)

    lines = []

    used_line = Text("Usage:   {:5.1f}% ".format(used_pct), style="bold")
    used_line.append(bar(used_pct), style="cyan")
    lines.append(used_line)

    elapsed_line = Text("Elapsed: {:5.1f}% ".format(elapsed_pct), style="bold")
    elapsed_line.append(bar(elapsed_pct), style="magenta")
    lines.append(elapsed_line)

    pace_line = Text("\nPace: {}".format(pace), style="bold {}".format(pace_color(pace)))
    pace_line.append("   Resets in: {}".format(format_duration(resets_at - now)), style="dim")
    try:
        mtime = os.path.getmtime(STATE_PATH)
        if is_stale(mtime, now):
            pace_line.append("  [STALE]", style="dim")
    except FileNotFoundError:
        pass
    lines.append(pace_line)

    values = [s["used_percentage"] for s in history]
    if values:
        lines.append(Text("\n{}".format(sparkline(values)), style="cyan"))

    heatmap_result = render_heatmap(window_history or [], used_pct, resets_at, now)
    if heatmap_result:
        cube_line, timeline = heatmap_result
        prefixed_cube_line = Text("\n")
        prefixed_cube_line.append_text(cube_line)
        lines.append(prefixed_cube_line)
        lines.append(timeline)

    if live_stats:
        stats_text = "\nTokens/min: {:,.0f}   Active sessions: {}".format(
            live_stats["tokens_per_minute"], live_stats["active_sessions"]
        )
        lines.append(Text(stats_text, style="bold"))

    if last_quote:
        quote_text, philosopher = last_quote
        lines.append(Text("\n· \"{}\" —{} ·".format(quote_text, philosopher), style="dim italic"))

    return Panel(Group(*lines), title="claudemaxxing (5h window)", height=console.height)


def main():
    console.clear()
    last_pace = None
    last_quote = None

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            state = read_state()
            history = read_history()
            window_history = read_history(WINDOW_HISTORY_PATH)
            live_stats = {
                "tokens_per_minute": tokens_per_minute(),
                "active_sessions": count_active_claude_sessions(),
            }

            if state is not None:
                now = time.time()
                elapsed_pct = compute_elapsed_percentage(state["resets_at"], now)
                pace = compute_pace(state["used_percentage"], elapsed_pct)
                if pace != last_pace:
                    last_quote = pick_quote(QUOTE_POOLS[pace])
                    last_pace = pace

            live.update(render(state, history, last_quote, live_stats, window_history))
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
