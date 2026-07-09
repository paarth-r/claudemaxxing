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


from model_burn import suggest, apply_estimates

AVGS = {
    "fable":  {"rate": 0.9, "minutes": 60.0},
    "opus":   {"rate": 0.5, "minutes": 60.0},
    "sonnet": {"rate": 0.2, "minutes": 60.0},
    "haiku":  {"rate": 0.05, "minutes": 60.0},
}

def test_apply_estimates_scales_unmeasured_models_from_anchor():
    # sonnet measured at 0.36%/min with enough minutes; price weights are
    # haiku 1 : sonnet 3 : opus 5 : fable 10, so unit = 0.12
    averages = {"sonnet": {"rate": 0.36, "minutes": 31.0},
                "opus": {"rate": 4.8, "minutes": 1.0}}  # noisy, sub-eligible
    blended = apply_estimates(averages)
    assert blended["sonnet"] == {"rate": 0.36, "minutes": 31.0, "estimated": False}
    assert blended["opus"]["estimated"] is True
    assert abs(blended["opus"]["rate"] - 0.6) < 1e-9  # estimate replaces the 4.8 noise
    assert abs(blended["fable"]["rate"] - 1.2) < 1e-9
    assert abs(blended["haiku"]["rate"] - 0.12) < 1e-9

def test_apply_estimates_prefers_the_best_measured_anchor():
    averages = {"sonnet": {"rate": 0.3, "minutes": 60.0},
                "opus": {"rate": 0.5, "minutes": 20.0}}
    blended = apply_estimates(averages)
    # both eligible and measured; estimates for the rest anchor on sonnet (most minutes)
    assert blended["opus"] == {"rate": 0.5, "minutes": 20.0, "estimated": False}
    assert abs(blended["fable"]["rate"] - 1.0) < 1e-9  # 0.3/3 * 10

def test_apply_estimates_no_anchor_yields_nothing():
    assert apply_estimates({"fable": {"rate": 0.9, "minutes": 2.0}}) == {}
    assert apply_estimates({}) == {}

def test_apply_estimates_keeps_measured_unknown_models():
    averages = {"sonnet": {"rate": 0.3, "minutes": 60.0},
                "claude-newthing-9": {"rate": 0.7, "minutes": 15.0}}
    blended = apply_estimates(averages)
    assert blended["claude-newthing-9"] == {"rate": 0.7, "minutes": 15.0, "estimated": False}

def test_suggest_collecting_data_when_no_rates():
    assert suggest("BELOW", 0.5, 0.1, 20, 120, None, {}) == "collecting data"
    # composition: sparse measurements with no eligible anchor -> no rates
    sparse = apply_estimates({"fable": {"rate": 0.9, "minutes": 2.0}})
    assert suggest("BELOW", 0.5, 0.1, 20, 120, "fable", sparse) == "collecting data"

def test_suggest_below_one_more_session_of_heaviest_that_fits():
    # used 20%, rate 0.1%/min, 120m left -> surplus = 80 - 12 = 68%
    # fable session costs 0.9*30 = 27% <= 68 -> fits, and it's the heaviest
    assert suggest("BELOW", 0.5, 0.1, 20, 120, "sonnet", AVGS) == "one more fable session"

def test_suggest_below_smaller_session_when_surplus_is_tight():
    # used 88%, rate 0.05%/min, 60m left -> surplus = 12 - 3 = 9%
    # fable 27% no, opus 15% no, sonnet 6% yes
    assert suggest("BELOW", 0.2, 0.05, 88, 60, "haiku", AVGS) == "one more sonnet session"

def test_suggest_below_switch_up_when_no_session_fits():
    # used 99%, rate 0.0%/min, 10m left -> surplus = 1%. Cheapest session is
    # haiku at 0.05*30 = 1.5% - nothing fits. Ideal is 0.1%/min; the only
    # faster-than-current model closer to ideal than 0.0 is haiku (0.05).
    assert suggest("BELOW", 0.1, 0.0, 99, 10, "sonnet", AVGS) == "switch to haiku"

def test_suggest_below_stays_when_already_on_the_only_candidate():
    # surplus = (100-99.5) - 0.04*10 = 0.1%; a haiku session costs 1.5% - no
    # fit. haiku's rate would qualify for switch-up, but it IS the current
    # model - "switching" to the model already in use must read as staying.
    only = {"haiku": {"rate": 0.05, "minutes": 60.0}}
    assert suggest("BELOW", 0.5, 0.04, 99.5, 10, "haiku", only) == "stay on haiku"

def test_suggest_above_switches_to_heaviest_that_fits_ideal():
    assert suggest("ABOVE", 0.3, 0.9, 50, 100, "fable", AVGS) == "switch to sonnet"

def test_suggest_above_stay_when_current_already_fits():
    assert suggest("ABOVE", 0.3, 0.9, 50, 100, "sonnet", AVGS) == "stay on sonnet"

def test_suggest_above_ease_off_when_even_lightest_overshoots():
    assert suggest("ABOVE", 0.01, 0.9, 50, 100, "fable", AVGS) == "ease off - even haiku overshoots"

def test_suggest_at_stays_on_current():
    assert suggest("AT", 0.5, 0.5, 50, 100, "opus", AVGS) == "stay on opus"

def test_suggest_at_unknown_current_falls_back_to_closest_to_ideal():
    assert suggest("AT", 0.5, 0.5, 50, 100, None, AVGS) == "stay on opus"


from model_burn import gather_model_stats
from state_io import read_history as read_burn_history

def test_gather_model_stats_persists_clean_samples_and_advances_cursor(tmp_path):
    burn_path = str(tmp_path / "model_burn.jsonl")
    cursor_path = str(tmp_path / "cursor.json")
    history = [_h(100, 10), _h(160, 11)]
    tokens = [(120, 500, "claude-opus-4-8")]

    result = gather_model_stats(history, now=200, burn_path=burn_path,
                                cursor_path=cursor_path, token_samples_fn=lambda cutoff: tokens)
    stored = read_burn_history(path=burn_path)
    assert len(stored) == 1 and stored[0]["model"] == "opus"
    assert result["current_model"] == "opus"
    assert result["averages"]["opus"]["rate"] == 1.0

    # Second call with unchanged history: cursor prevents double-counting.
    gather_model_stats(history, now=260, burn_path=burn_path,
                       cursor_path=cursor_path, token_samples_fn=lambda cutoff: tokens)
    assert len(read_burn_history(path=burn_path)) == 1

def test_gather_model_stats_discards_mixed_intervals_but_still_advances(tmp_path):
    burn_path = str(tmp_path / "model_burn.jsonl")
    cursor_path = str(tmp_path / "cursor.json")
    history = [_h(100, 10), _h(160, 11)]
    tokens = [(120, 500, "claude-opus-4-8"), (130, 500, "claude-sonnet-5")]

    gather_model_stats(history, now=200, burn_path=burn_path,
                       cursor_path=cursor_path, token_samples_fn=lambda cutoff: tokens)
    assert read_burn_history(path=burn_path) == []
    # New interval later gets processed; the old mixed one is never rescanned.
    history.append(_h(220, 12))
    gather_model_stats(history, now=300, burn_path=burn_path,
                       cursor_path=cursor_path, token_samples_fn=lambda cutoff: [(180, 100, "claude-opus-4-8")])
    stored = read_burn_history(path=burn_path)
    assert len(stored) == 1 and stored[0]["t0"] == 160

def test_gather_model_stats_recovers_from_lost_cursor_without_duplicates(tmp_path):
    # A corrupt/deleted cursor must not double-count: re-mined intervals that
    # are already stored get skipped by their (t0, t1) identity.
    burn_path = str(tmp_path / "model_burn.jsonl")
    cursor_path = str(tmp_path / "cursor.json")
    history = [_h(100, 10), _h(160, 11)]
    tokens = [(120, 500, "claude-opus-4-8")]
    gather_model_stats(history, now=200, burn_path=burn_path,
                       cursor_path=cursor_path, token_samples_fn=lambda cutoff: tokens)
    os.remove(cursor_path)
    gather_model_stats(history, now=260, burn_path=burn_path,
                       cursor_path=cursor_path, token_samples_fn=lambda cutoff: tokens)
    assert len(read_burn_history(path=burn_path)) == 1

from model_burn import heaviest_session, suggest_hot_session_action, SESSION_WINDOW_SECONDS

def test_heaviest_session_picks_highest_token_count():
    def fake_snapshots(cutoff):
        return [
            {"session_id": "sess-a", "project": "hyperform", "tokens": 500, "dominant_model": "claude-opus-4-8"},
            {"session_id": "sess-b", "project": "storepose", "tokens": 12000, "dominant_model": "claude-haiku-4-5"},
        ]
    result = heaviest_session(now=1000, snapshot_fn=fake_snapshots)
    assert result["session_id"] == "sess-b"
    assert result["project"] == "storepose"
    assert result["model"] == "haiku"
    assert result["tokens_per_minute"] == 12000 / (SESSION_WINDOW_SECONDS / 60)

def test_heaviest_session_none_when_no_snapshots():
    assert heaviest_session(now=1000, snapshot_fn=lambda cutoff: []) is None

def test_heaviest_session_unattributed_model_is_none():
    def fake_snapshots(cutoff):
        return [{"session_id": "sess-a", "project": "proj", "tokens": 100, "dominant_model": None}]
    result = heaviest_session(now=1000, snapshot_fn=fake_snapshots)
    assert result["model"] is None


HOT = {"session_id": "sess-a12345", "project": "hyperform", "model": "opus", "tokens_per_minute": 9000}

def test_suggest_hot_session_none_when_not_above():
    assert suggest_hot_session_action("AT", 0.3, HOT, AVGS) is None
    assert suggest_hot_session_action("BELOW", 0.3, HOT, AVGS) is None

def test_suggest_hot_session_none_when_no_hot_session():
    assert suggest_hot_session_action("ABOVE", 0.3, None, AVGS) is None

def test_suggest_hot_session_switches_to_heaviest_fitting_model():
    assert suggest_hot_session_action("ABOVE", 0.3, HOT, AVGS) == "switch hyperform (sess-a12) to sonnet"

def test_suggest_hot_session_kills_when_nothing_fits():
    assert suggest_hot_session_action("ABOVE", 0.01, HOT, AVGS) == "kill hyperform (sess-a12) - heaviest session"

def test_suggest_hot_session_kills_when_no_rates():
    assert suggest_hot_session_action("ABOVE", 0.3, HOT, {}) == "kill hyperform (sess-a12) - heaviest session"

def test_suggest_hot_session_kills_when_already_on_best_fit():
    only = {"opus": {"rate": 0.5, "minutes": 60.0}}
    assert suggest_hot_session_action("ABOVE", 0.6, HOT, only) == "kill hyperform (sess-a12) - heaviest session"


def test_gather_model_stats_empty_history(tmp_path):
    result = gather_model_stats([], now=200,
                                burn_path=str(tmp_path / "b.jsonl"),
                                cursor_path=str(tmp_path / "c.json"),
                                token_samples_fn=lambda cutoff: [])
    assert result == {"averages": {}, "current_model": None}
