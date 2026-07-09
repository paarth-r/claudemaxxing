import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stats import compute_tokens_per_minute, count_sessions_from_ps_lines, recent_token_samples

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


def _write_jsonl_line(f, timestamp_epoch, usage):
    import datetime
    ts_str = datetime.datetime.utcfromtimestamp(timestamp_epoch).isoformat() + "Z"
    f.write(json.dumps({"timestamp": ts_str, "message": {"role": "assistant", "usage": usage}}) + "\n")


def test_recent_token_samples_finds_data_beyond_a_small_initial_tail_guess(tmp_path):
    # A message that's still within the cutoff window but gets buried behind
    # a burst of large, even-more-recent messages must not be lost just
    # because a fixed-size tail read was too small to reach it.
    # (tail_bytes is passed explicitly - it's a default-bound-at-def-time
    # parameter, so monkeypatching the module constant wouldn't affect it.)
    path = tmp_path / "session.jsonl"
    now = time.time()
    with open(path, "w") as f:
        # Old, out-of-window padding (correctly excluded either way).
        for i in range(50):
            _write_jsonl_line(f, now - 10000, {"input_tokens": 1, "output_tokens": 1, "padding": "x" * 50})
        # Within the 300s cutoff window, but buried behind a large recent burst below.
        _write_jsonl_line(f, now - 280, {"input_tokens": 7, "output_tokens": 13})
        # A burst of large, very recent messages (e.g. big tool output) that would
        # push the line above outside a small fixed-size tail read.
        for i in range(50):
            _write_jsonl_line(f, now - 10, {"input_tokens": 1, "output_tokens": 1, "padding": "y" * 50})

    cutoff = now - 300
    samples = recent_token_samples(cutoff=cutoff, projects_dir=str(tmp_path), tail_bytes=200)
    recent = [s for s in samples if s[0] >= cutoff]
    buried_message_tokens = [t for ts, t in recent if t == 20]
    assert buried_message_tokens == [20], "the buried-but-in-window message must still be counted"

def test_recent_token_samples_excludes_cache_read_tokens(tmp_path):
    import stats
    path = tmp_path / "session.jsonl"
    now = time.time()
    with open(path, "w") as f:
        _write_jsonl_line(f, now - 10, {
            "input_tokens": 2, "output_tokens": 3,
            "cache_creation_input_tokens": 5, "cache_read_input_tokens": 999999,
        })
    samples = stats.recent_token_samples(cutoff=now - 300, projects_dir=str(tmp_path))
    assert samples == [(samples[0][0], 10)]  # 2+3+5, cache_read excluded
