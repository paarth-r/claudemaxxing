import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from monitor import sparkline, render, SPARK_CHARS


def test_sparkline_empty_is_empty_string():
    assert sparkline([]) == ""

def test_sparkline_uses_full_history_without_max_width():
    assert len(sparkline([1] * 100)) == 100

def test_sparkline_truncates_to_max_width_keeping_most_recent():
    # 0..99, ascending - the most recent (highest) values must survive.
    values = list(range(100))
    result = sparkline(values, max_width=10)
    assert len(result) == 10
    assert result[-1] == SPARK_CHARS[-1]  # value 99 is the max -> top spark char

def test_sparkline_max_width_larger_than_data_is_a_no_op():
    assert sparkline([1, 2, 3], max_width=60) == sparkline([1, 2, 3])


def _panel_text(panel):
    group = panel.renderable
    return "\n".join(getattr(r, "plain", "") for r in group.renderables)

def _model_stats():
    return {"averages": {"opus": {"rate": 0.5, "minutes": 60.0}}, "current_model": "opus"}

def test_render_shows_nothing_from_model_burn_at_at_pace():
    now = time.time()
    # ideal_rate = (100-50)/100 = 0.5%/min; history sample yields the same
    # current_rate (45 -> 50 over 10 minutes = 0.5%/min) - lands exactly AT.
    state = {"used_percentage": 50, "resets_at": now + 6000}
    history = [{"timestamp": now - 600, "used_percentage": 45, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], _model_stats(), None)
    text = _panel_text(panel)
    assert "Pace: AT" in text
    assert "SUGGEST" not in text
    assert "Model burn" not in text

def test_render_shows_suggestion_at_above_pace():
    now = time.time()
    state = {"used_percentage": 90, "resets_at": now + 6000}
    history = [{"timestamp": now - 60, "used_percentage": 85, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], _model_stats(), None)
    text = _panel_text(panel)
    assert "Pace: ABOVE" in text
    assert "SUGGEST" in text
