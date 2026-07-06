import json
import os

STATE_PATH = os.path.expanduser("~/.claude/usage-monitor/state.json")
HISTORY_PATH = os.path.expanduser("~/.claude/usage-monitor/history.jsonl")


def _ensure_parent_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def read_state(path=STATE_PATH):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def write_state(snapshot, path=STATE_PATH):
    _ensure_parent_dir(path)
    with open(path, "w") as f:
        json.dump(snapshot, f)


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
    _ensure_parent_dir(path)
    with open(path, "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")
