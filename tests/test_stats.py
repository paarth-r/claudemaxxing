import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stats import compute_tokens_per_minute, count_sessions_from_ps_lines

def test_compute_tokens_per_minute_sums_within_window():
    now = 1000
    samples = [
        (now - 30, 100),   # inside 5-min window
        (now - 250, 200),  # inside window
        (now - 400, 500),  # outside 5-min (300s) window
    ]
    rate = compute_tokens_per_minute(samples, now=now, window_seconds=300)
    assert rate == (100 + 200) / 5

def test_compute_tokens_per_minute_no_samples_is_zero():
    assert compute_tokens_per_minute([], now=1000, window_seconds=300) == 0

def test_count_sessions_from_ps_lines_counts_foreground_claude_only():
    lines = [
        "paarth-r 111  0.1  0.1 1 1 s001 S+ 9:00AM 0:01.00 claude",
        "paarth-r 112  0.1  0.1 1 1 s005 S+ 9:00AM 0:01.00 claude --dangerously-skip-permissions",
        "paarth-r 113  0.1  0.1 1 1 ??   S  9:00AM 0:01.00 /Users/x/.local/share/claude/versions/2.1.201 --resume foo.jsonl",
        "paarth-r 114  0.1  0.1 1 1 ??   Ss 9:00AM 0:01.00 /Users/x/.local/bin/claude daemon run --origin transient",
        "paarth-r 115  0.1  0.1 1 1 s003 S+ 9:00AM 0:01.00 bun run --cwd /plugins/imessage start",
    ]
    assert count_sessions_from_ps_lines(lines) == 2

def test_count_sessions_from_ps_lines_empty():
    assert count_sessions_from_ps_lines([]) == 0
