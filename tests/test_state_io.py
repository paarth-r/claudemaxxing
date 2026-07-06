import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state_io import read_state, read_history, write_state, append_history, prune_history

def test_read_state_missing_file_returns_none(tmp_path):
    assert read_state(str(tmp_path / "missing.json")) is None

def test_write_then_read_state_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    write_state({"used_percentage": 42, "resets_at": 123}, path)
    assert read_state(path) == {"used_percentage": 42, "resets_at": 123}

def test_read_history_missing_file_returns_empty_list(tmp_path):
    assert read_history(str(tmp_path / "missing.jsonl")) == []

def test_append_and_read_history(tmp_path):
    path = str(tmp_path / "history.jsonl")
    append_history({"timestamp": 1, "used_percentage": 10, "resets_at": 100}, path)
    append_history({"timestamp": 2, "used_percentage": 20, "resets_at": 100}, path)
    samples = read_history(path)
    assert len(samples) == 2
    assert samples[0]["used_percentage"] == 10
    assert samples[1]["used_percentage"] == 20

def test_read_history_skips_corrupt_lines(tmp_path):
    path = str(tmp_path / "history.jsonl")
    with open(path, "w") as f:
        f.write('{"timestamp": 1, "used_percentage": 10, "resets_at": 100}\n')
        f.write("not json\n")
        f.write('{"timestamp": 2, "used_percentage": 20, "resets_at": 100}\n')
    samples = read_history(path)
    assert len(samples) == 2

def test_prune_history_drops_expired_windows(tmp_path):
    path = str(tmp_path / "history.jsonl")
    append_history({"timestamp": 1, "used_percentage": 10, "resets_at": 50}, path)
    append_history({"timestamp": 2, "used_percentage": 20, "resets_at": 200}, path)
    prune_history(now=100, path=path)
    samples = read_history(path)
    assert len(samples) == 1
    assert samples[0]["resets_at"] == 200
