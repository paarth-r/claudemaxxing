import json
import os
import subprocess
import time
from datetime import datetime

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
TAIL_BYTES = 131072
MAX_TAIL_BYTES = 16 * 1024 * 1024


def compute_tokens_per_minute(samples, now, window_seconds=300):
    """samples: list of (timestamp, token_count) tuples. Pure/testable core."""
    total = sum(tokens for ts, tokens in samples if now - ts <= window_seconds)
    return total / (window_seconds / 60)


def _parse_iso_timestamp(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def _read_tail_lines(path, cutoff, initial_bytes, max_bytes):
    """Read lines from the tail of an append-only file, doubling the read
    window until the earliest line in it predates cutoff (proving nothing
    relevant was missed) or the whole file has been read. A fixed-size tail
    read can silently undercount if a burst of large recent messages (e.g.
    verbose tool output) pushes an older-but-still-in-window message beyond
    it - this guarantees correctness instead of hoping the guess was big enough.
    """
    size = os.path.getsize(path)
    read_size = min(initial_bytes, size)

    while True:
        with open(path, "rb") as f:
            if read_size < size:
                f.seek(size - read_size)
                f.readline()  # discard the partial line at the seek point
            lines = f.readlines()

        if read_size >= size or read_size >= max_bytes:
            return lines

        earliest_ts = None
        for raw_line in lines:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso_timestamp(obj.get("timestamp"))
            if ts is not None:
                earliest_ts = ts
                break  # file is append-only/chronological - first parseable line is earliest

        if earliest_ts is not None and earliest_ts < cutoff:
            return lines

        read_size = min(read_size * 4, size, max_bytes)


def _file_token_samples(path, cutoff, tail_bytes, max_tail_bytes):
    """(timestamp, token_count, model) samples newer than cutoff in one
    transcript file. Deliberately excludes cache_read_input_tokens: that
    field re-bills the entire cached context on every message and stays
    huge/roughly-constant for a long conversation, drowning out the actual
    new-work signal."""
    samples = []
    for raw_line in _read_tail_lines(path, cutoff, tail_bytes, max_tail_bytes):
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = obj.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        ts = _parse_iso_timestamp(obj.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        total_tokens = (
            usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
        samples.append((ts, total_tokens, message.get("model")))
    return samples


def recent_token_samples(cutoff, projects_dir=PROJECTS_DIR, tail_bytes=TAIL_BYTES, max_tail_bytes=MAX_TAIL_BYTES):
    """Scan recently-modified transcript files for (timestamp, token_count,
    model) samples newer than cutoff, flattened across all sessions."""
    samples = []
    if not os.path.isdir(projects_dir):
        return samples

    for root, _dirs, files in os.walk(projects_dir):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    continue
                samples.extend(_file_token_samples(path, cutoff, tail_bytes, max_tail_bytes))
            except OSError:
                continue
    return samples


def session_snapshots(cutoff, projects_dir=PROJECTS_DIR, tail_bytes=TAIL_BYTES, max_tail_bytes=MAX_TAIL_BYTES):
    """One entry per transcript file with token activity since cutoff - lets
    the caller see which individual Claude Code session is driving usage,
    not just the aggregate. dominant_model is whichever model produced the
    most tokens in-window for that session (None if none were attributed).
    project prefers the transcript's own "cwd" field over the on-disk
    project directory name, which Claude Code encodes as the full absolute
    path with "/" -> "-" (e.g. "-Users-x-Code-myrepo") - not something a
    user recognizes at a glance."""
    snapshots = []
    if not os.path.isdir(projects_dir):
        return snapshots

    for root, _dirs, files in os.walk(projects_dir):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    continue
                raw_lines = _read_tail_lines(path, cutoff, tail_bytes, max_tail_bytes)
            except OSError:
                continue

            tokens = 0
            model_totals = {}
            cwd = None
            for raw_line in raw_lines:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cwd is None and isinstance(obj.get("cwd"), str):
                    cwd = obj["cwd"]
                message = obj.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                ts = _parse_iso_timestamp(obj.get("timestamp"))
                if ts is None or ts < cutoff:
                    continue
                total_tokens = (
                    usage.get("input_tokens", 0)
                    + usage.get("output_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                )
                tokens += total_tokens
                model = message.get("model")
                if model:
                    model_totals[model] = model_totals.get(model, 0) + total_tokens

            if tokens <= 0:
                continue
            dominant_model = max(model_totals, key=model_totals.get) if model_totals else None
            snapshots.append({
                "session_id": name[:-len(".jsonl")],
                "project": os.path.basename(cwd) if cwd else os.path.basename(root),
                "tokens": tokens,
                "dominant_model": dominant_model,
            })
    return snapshots


def tokens_per_minute(window_seconds=300):
    now = time.time()
    samples = recent_token_samples(cutoff=now - window_seconds)
    pairs = [(ts, tokens) for ts, tokens, _model in samples]
    return compute_tokens_per_minute(pairs, now=now, window_seconds=window_seconds)


def count_sessions_from_ps_lines(lines):
    """A 'session' is a foreground claude CLI process attached to a real
    terminal - excludes background workers, the daemon, and unrelated
    processes that merely happen to have 'claude' in a path."""
    count = 0
    for line in lines:
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        tty = parts[6]
        command = parts[10]
        if tty == "??":
            continue
        first_token = command.split()[0]
        basename = os.path.basename(first_token)
        if basename != "claude":
            continue
        if "daemon" in command or "--bg-" in command:
            continue
        count += 1
    return count


def count_active_claude_sessions():
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    lines = out.splitlines()[1:]  # drop header
    return count_sessions_from_ps_lines(lines)
