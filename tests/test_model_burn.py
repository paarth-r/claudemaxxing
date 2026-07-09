import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from model_burn import normalize_model_id, build_intervals


def test_normalize_model_id_known_models():
    assert normalize_model_id("claude-fable-5") == "fable"
    assert normalize_model_id("claude-opus-4-8") == "opus"
    assert normalize_model_id("claude-sonnet-5") == "sonnet"
    assert normalize_model_id("claude-haiku-4-5-20251001") == "haiku"

def test_normalize_model_id_unknown_passes_through():
    assert normalize_model_id("claude-newthing-9") == "claude-newthing-9"

def test_normalize_model_id_empty_is_none():
    assert normalize_model_id(None) is None
    assert normalize_model_id("") is None


def _h(ts, pct, resets_at=10000):
    return {"timestamp": ts, "used_percentage": pct, "resets_at": resets_at}

def test_build_intervals_pairs_consecutive_samples():
    history = [_h(100, 10), _h(160, 11), _h(280, 13)]
    intervals = build_intervals(history, last_processed=0)
    assert intervals == [
        {"t0": 100, "t1": 160, "delta_pct": 1, "duration_minutes": 1.0},
        {"t0": 160, "t1": 280, "delta_pct": 2, "duration_minutes": 2.0},
    ]

def test_build_intervals_respects_cursor():
    history = [_h(100, 10), _h(160, 11), _h(280, 13)]
    intervals = build_intervals(history, last_processed=160)
    assert [i["t0"] for i in intervals] == [160]

def test_build_intervals_skips_window_resets():
    history = [_h(100, 90, resets_at=10000), _h(160, 1, resets_at=28000)]
    assert build_intervals(history, last_processed=0) == []

def test_build_intervals_skips_idle_gaps_and_negative_deltas():
    # 30-minute gap exceeds MAX_INTERVAL_MINUTES (20) - an idle stretch
    # would dilute the burn rate, so it is discarded.
    history = [_h(100, 10), _h(100 + 1800, 12)]
    assert build_intervals(history, last_processed=0) == []
    history = [_h(100, 10), _h(160, 9)]
    assert build_intervals(history, last_processed=0) == []
