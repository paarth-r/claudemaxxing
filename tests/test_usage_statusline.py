import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_statusline import build_snapshot, format_statusline

def test_build_snapshot_extracts_five_hour_fields():
    payload = {"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": 999}}}
    snapshot = build_snapshot(payload, now=100)
    assert snapshot == {"timestamp": 100, "used_percentage": 42, "resets_at": 999}

def test_build_snapshot_returns_none_when_five_hour_absent():
    assert build_snapshot({"rate_limits": {}}, now=100) is None
    assert build_snapshot({}, now=100) is None

def test_format_statusline():
    assert format_statusline(42) == "5h: 42% used"
