import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_statusline import merge_snapshot

def test_merge_with_no_existing_returns_incoming():
    incoming = {"used_percentage": 40, "resets_at": 100}
    assert merge_snapshot(None, incoming) == incoming

def test_merge_prefers_higher_used_percentage_same_window():
    existing = {"used_percentage": 62, "resets_at": 100}
    incoming = {"used_percentage": 53, "resets_at": 100}
    assert merge_snapshot(existing, incoming) == existing

def test_merge_prefers_incoming_when_it_is_higher_same_window():
    existing = {"used_percentage": 53, "resets_at": 100}
    incoming = {"used_percentage": 62, "resets_at": 100}
    assert merge_snapshot(existing, incoming) == incoming

def test_merge_prefers_incoming_on_equal_percentage():
    existing = {"used_percentage": 62, "resets_at": 100}
    incoming = {"used_percentage": 62, "resets_at": 100}
    assert merge_snapshot(existing, incoming) == incoming

def test_merge_prefers_incoming_when_window_has_reset():
    existing = {"used_percentage": 99, "resets_at": 100}
    incoming = {"used_percentage": 2, "resets_at": 999}
    assert merge_snapshot(existing, incoming) == incoming
