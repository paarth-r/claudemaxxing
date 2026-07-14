from hookkit.queue import drain, peek, push


def test_push_then_peek(repo):
    push(repo / ".brain", "corrections", {"prompt": "never use mp4v"})
    items = peek(repo / ".brain", "corrections")
    assert len(items) == 1
    assert items[0]["prompt"] == "never use mp4v"


def test_peek_does_not_empty_the_queue(repo):
    push(repo / ".brain", "corrections", {"prompt": "x"})
    peek(repo / ".brain", "corrections")
    assert len(peek(repo / ".brain", "corrections")) == 1


def test_drain_returns_and_empties(repo):
    push(repo / ".brain", "pain", {"cmd": "npm run build"})
    assert len(drain(repo / ".brain", "pain")) == 1
    assert peek(repo / ".brain", "pain") == []


def test_missing_queue_is_empty(repo):
    assert peek(repo / ".brain", "nothing-here") == []
    assert drain(repo / ".brain", "nothing-here") == []


def test_queues_are_independent(repo):
    push(repo / ".brain", "corrections", {"prompt": "a"})
    push(repo / ".brain", "pain", {"cmd": "b"})
    assert len(peek(repo / ".brain", "corrections")) == 1
    assert len(peek(repo / ".brain", "pain")) == 1


def test_corrupt_line_is_skipped(repo):
    push(repo / ".brain", "corrections", {"prompt": "good"})
    path = repo / ".brain" / "_queue" / "corrections.jsonl"
    with path.open("a") as handle:
        handle.write("{not json\n")
    assert len(peek(repo / ".brain", "corrections")) == 1


def test_push_to_unwritable_brain_is_silent(tmp_path):
    push(tmp_path / "does" / "not" / "exist", "corrections", {"prompt": "x"})  # must not raise


def test_a_failed_drain_does_not_lose_items(repo):
    """Items are only cleared once they have been read out successfully."""
    push(repo / ".brain", "corrections", {"prompt": "keep me"})
    items = drain(repo / ".brain", "corrections")
    assert items[0]["prompt"] == "keep me"
