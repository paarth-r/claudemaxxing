import os
import time

from hookkit.receipts import (
    append,
    attempt_key,
    is_fresh,
    newest_mtime,
    record_denial,
    records,
    was_denied,
)

SESSION = "sess-1"


def _brain(repo):
    return repo / ".brain"


def _touch(path, when):
    path.write_text("changed\n")
    os.utime(path, (when, when))


def test_append_and_read_back(repo):
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    entries = records(_brain(repo), SESSION)
    assert len(entries) == 1
    assert entries[0]["kind"] == "live-run"
    assert entries[0]["exit"] == 0


def test_records_empty_for_unknown_session(repo):
    assert records(_brain(repo), "nope") == []


def test_no_receipt_is_not_fresh(repo):
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is False


def test_failed_run_does_not_count(repo):
    append(_brain(repo), SESSION, "live-run", "./run.sh", 1)
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is False


def test_receipt_newer_than_source_is_fresh(repo):
    _touch(repo / "src" / "main.py", time.time() - 100)
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is True


def test_receipt_older_than_source_is_stale(repo):
    """THE test. A live run from before the last edit must not satisfy the rule."""
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    _touch(repo / "src" / "main.py", time.time() + 10)
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is False


def test_receipt_of_wrong_kind_does_not_satisfy(repo):
    _touch(repo / "src" / "main.py", time.time() - 100)
    append(_brain(repo), SESSION, "unit-tests", "pytest", 0)
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is False


def test_no_fresher_than_means_any_receipt_counts(repo):
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    assert is_fresh(_brain(repo), SESSION, "live-run", None, repo) is True


def test_glob_matching_nothing_means_any_receipt_counts(repo):
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    assert is_fresh(_brain(repo), SESSION, "live-run", "nonexistent/**", repo) is True


def test_newest_mtime_none_when_nothing_matches(repo):
    assert newest_mtime(repo, "nothing/here/**") is None


def test_newest_mtime_finds_the_newest(repo):
    _touch(repo / "src" / "main.py", 1000.0)
    _touch(repo / "src" / "other.py", 2000.0)
    assert newest_mtime(repo, "src/**") == 2000.0


def test_nested_source_edit_is_seen(repo):
    """A glob like src/** must reach files in subdirectories, not just the top level."""
    nested = repo / "src" / "deep" / "deeper"
    nested.mkdir(parents=True)
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    _touch(nested / "buried.py", time.time() + 10)
    assert is_fresh(_brain(repo), SESSION, "live-run", "src/**", repo) is False


def test_denial_is_recorded_and_seen(repo):
    key = attempt_key("live-run-before-commit", "Bash", {"command": "git commit -m x"})
    assert was_denied(_brain(repo), SESSION, key) is False
    record_denial(_brain(repo), SESSION, key)
    assert was_denied(_brain(repo), SESSION, key) is True


def test_attempt_key_is_stable_for_identical_calls():
    a = attempt_key("r", "Bash", {"command": "git commit -m x"})
    b = attempt_key("r", "Bash", {"command": "git commit -m x"})
    assert a == b


def test_attempt_key_differs_for_different_commands():
    a = attempt_key("r", "Bash", {"command": "git commit -m x"})
    b = attempt_key("r", "Bash", {"command": "git commit -m y"})
    assert a != b


def test_attempt_key_differs_per_rule():
    a = attempt_key("rule-a", "Bash", {"command": "git commit"})
    b = attempt_key("rule-b", "Bash", {"command": "git commit"})
    assert a != b


def test_denial_of_one_call_does_not_release_another(repo):
    denied = attempt_key("r", "Bash", {"command": "git commit -m x"})
    other = attempt_key("r", "Bash", {"command": "git push"})
    record_denial(_brain(repo), SESSION, denied)
    assert was_denied(_brain(repo), SESSION, other) is False


def test_denials_are_scoped_to_a_session(repo):
    key = attempt_key("r", "Bash", {"command": "git commit -m x"})
    record_denial(_brain(repo), SESSION, key)
    assert was_denied(_brain(repo), "a-different-session", key) is False


def test_corrupt_line_is_skipped_not_raised(repo):
    append(_brain(repo), SESSION, "live-run", "./run.sh", 0)
    path = _brain(repo) / "_receipts" / f"{SESSION}.jsonl"
    with path.open("a") as handle:
        handle.write("{not json\n")
    assert len(records(_brain(repo), SESSION)) == 1
