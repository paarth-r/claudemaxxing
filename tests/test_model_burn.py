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


from model_burn import attribute_interval

INTERVAL = {"t0": 100, "t1": 160, "delta_pct": 1, "duration_minutes": 1.0}

def test_attribute_interval_single_model_is_clean():
    samples = [(120, 500, "claude-fable-5"), (150, 300, "claude-fable-5")]
    result = attribute_interval(INTERVAL, samples)
    assert result == {
        "model": "fable", "delta_pct": 1, "duration_minutes": 1.0,
        "tokens": 800, "t0": 100, "t1": 160,
    }

def test_attribute_interval_mixed_models_rejected():
    samples = [(120, 500, "claude-fable-5"), (150, 300, "claude-sonnet-5")]
    assert attribute_interval(INTERVAL, samples) is None

def test_attribute_interval_no_tokens_rejected():
    assert attribute_interval(INTERVAL, []) is None

def test_attribute_interval_ignores_samples_outside_interval():
    samples = [(90, 999, "claude-sonnet-5"), (120, 500, "claude-fable-5"), (200, 999, "claude-opus-4-8")]
    result = attribute_interval(INTERVAL, samples)
    assert result["model"] == "fable" and result["tokens"] == 500

def test_attribute_interval_ignores_model_less_samples():
    samples = [(120, 500, "claude-fable-5"), (130, 100, None)]
    result = attribute_interval(INTERVAL, samples)
    assert result["model"] == "fable" and result["tokens"] == 500


from model_burn import compute_averages, eligible_models, detect_current_model

def _burn(model, delta, minutes):
    return {"model": model, "delta_pct": delta, "duration_minutes": minutes,
            "tokens": 100, "t0": 0, "t1": 0}

def test_compute_averages_is_duration_weighted():
    samples = [_burn("fable", 1, 1.0), _burn("fable", 5, 9.0), _burn("haiku", 1, 10.0)]
    averages = compute_averages(samples)
    assert averages["fable"] == {"rate": 0.6, "minutes": 10.0}  # 6% over 10m, not mean(1, 5/9)
    assert averages["haiku"] == {"rate": 0.1, "minutes": 10.0}

def test_compute_averages_empty():
    assert compute_averages([]) == {}

def test_eligible_models_requires_minimum_minutes():
    averages = {"fable": {"rate": 0.6, "minutes": 10.0}, "opus": {"rate": 0.4, "minutes": 9.9}}
    assert list(eligible_models(averages)) == ["fable"]

def test_detect_current_model_picks_dominant_recent_model():
    now = 1000
    samples = [
        (now - 30, 500, "claude-fable-5"),
        (now - 60, 100, "claude-sonnet-5"),
        (now - 700, 9999, "claude-opus-4-8"),  # outside 600s lookback
    ]
    assert detect_current_model(samples, now) == "fable"

def test_detect_current_model_none_when_quiet():
    assert detect_current_model([], now=1000) is None
