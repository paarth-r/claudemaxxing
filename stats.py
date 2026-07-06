import json
import os
import subprocess
import time
from datetime import datetime

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
TAIL_BYTES = 131072


def compute_tokens_per_minute(samples, now, window_seconds=300):
    """samples: list of (timestamp, token_count) tuples. Pure/testable core."""
    total = sum(tokens for ts, tokens in samples if now - ts <= window_seconds)
    return total / (window_seconds / 60)


def _parse_iso_timestamp(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def recent_token_samples(cutoff, projects_dir=PROJECTS_DIR, tail_bytes=TAIL_BYTES):
    """Scan recently-modified transcript files for (timestamp, token_count)
    samples newer than cutoff. Only reads the tail of each file since
    relevant entries are always near the end of an append-only log."""
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
                size = os.path.getsize(path)
                with open(path, "rb") as f:
                    if size > tail_bytes:
                        f.seek(size - tail_bytes)
                        f.readline()
                    for raw_line in f:
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
                            + usage.get("cache_read_input_tokens", 0)
                        )
                        samples.append((ts, total_tokens))
            except OSError:
                continue
    return samples


def tokens_per_minute(window_seconds=300):
    now = time.time()
    samples = recent_token_samples(cutoff=now - window_seconds)
    return compute_tokens_per_minute(samples, now=now, window_seconds=window_seconds)


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
