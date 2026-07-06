import json
import os
import tempfile

STATE_PATH = os.path.expanduser("~/.claude/usage-monitor/state.json")
HISTORY_PATH = os.path.expanduser("~/.claude/usage-monitor/history.jsonl")
# Permanent log of completed 5h windows (never pruned) - read_history/append_history
# below are generic over path, so they work for this file too.
WINDOW_HISTORY_PATH = os.path.expanduser("~/.claude/usage-monitor/window_history.jsonl")


def _ensure_parent_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _atomic_write(path, contents):
    """Write via a temp file + rename so concurrent writers (multiple Claude
    Code sessions invoking the statusline hook at once) can never interleave
    and corrupt the file - the rename is atomic at the filesystem level."""
    _ensure_parent_dir(path)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(contents)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def read_state(path=STATE_PATH):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def write_state(snapshot, path=STATE_PATH):
    _atomic_write(path, json.dumps(snapshot))


def read_history(path=HISTORY_PATH):
    samples = []
    if not os.path.exists(path):
        return samples
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return samples


def append_history(sample, path=HISTORY_PATH):
    _ensure_parent_dir(path)
    with open(path, "a") as f:
        f.write(json.dumps(sample) + "\n")


def prune_history(now, path=HISTORY_PATH):
    samples = [s for s in read_history(path) if s.get("resets_at", 0) > now]
    contents = "".join(json.dumps(s) + "\n" for s in samples)
    _atomic_write(path, contents)
