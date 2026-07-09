import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_statusline import merge_snapshot, build_window_archive_entry

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

def test_merge_rejects_incoming_for_an_older_window():
    # A lagging session can report data for a window that has *already*
    # ended, after another session already advanced the shared state to the
    # next window. That stale reading must never regress the shared state
    # backward (it would corrupt window-history archiving into thinking the
    # current window "ended" prematurely).
    existing = {"used_percentage": 5, "resets_at": 999}
    incoming = {"used_percentage": 80, "resets_at": 100}  # older window, higher %
    assert merge_snapshot(existing, incoming) == existing

def test_build_window_archive_entry_none_when_no_existing():
    final_state = {"used_percentage": 10, "resets_at": 999}
    assert build_window_archive_entry(None, final_state, now=1000) is None

def test_build_window_archive_entry_none_when_same_window():
    existing = {"used_percentage": 40, "resets_at": 100}
    final_state = {"used_percentage": 45, "resets_at": 100}
    assert build_window_archive_entry(existing, final_state, now=1000) is None

def test_build_window_archive_entry_archives_old_window_on_reset():
    existing = {"used_percentage": 87, "resets_at": 100}
    final_state = {"used_percentage": 3, "resets_at": 999}
    entry = build_window_archive_entry(existing, final_state, now=1000)
    assert entry == {"resets_at": 100, "peak_usage_percentage": 87, "archived_at": 1000}
