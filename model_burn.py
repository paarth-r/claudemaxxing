import os

from state_io import read_state, write_state, read_history, append_history
from stats import recent_token_samples

# Permanent per-model burn samples (never pruned) and the processing cursor
# that prevents re-counting intervals across monitor restarts.
MODEL_BURN_PATH = os.path.expanduser("~/.claude/usage-monitor/model_burn.jsonl")
MODEL_BURN_CURSOR_PATH = os.path.expanduser("~/.claude/usage-monitor/model_burn_cursor.json")

KNOWN_MODEL_PREFIXES = [
    ("claude-fable", "fable"),
    ("claude-opus", "opus"),
    ("claude-sonnet", "sonnet"),
    ("claude-haiku", "haiku"),
]
MIN_ELIGIBLE_MINUTES = 10.0
NOMINAL_SESSION_MINUTES = 30.0
MAX_INTERVAL_MINUTES = 20.0
CURRENT_MODEL_LOOKBACK_SECONDS = 600


def normalize_model_id(model_id):
    if not model_id:
        return None
    for prefix, short in KNOWN_MODEL_PREFIXES:
        if model_id.startswith(prefix):
            return short
    return model_id


def build_intervals(history, last_processed):
    """Pair consecutive usage samples into not-yet-processed intervals within
    a single 5h window. Idle gaps longer than MAX_INTERVAL_MINUTES are
    discarded: history only records change events, so a 1% tick after a long
    quiet stretch says nothing about the rate while actually generating."""
    intervals = []
    for prev, cur in zip(history, history[1:]):
        if prev["timestamp"] < last_processed:
            continue
        if prev.get("resets_at") != cur.get("resets_at"):
            continue  # spans a window reset - usage% snaps back to ~0 there
        duration_minutes = (cur["timestamp"] - prev["timestamp"]) / 60
        delta_pct = cur["used_percentage"] - prev["used_percentage"]
        if duration_minutes <= 0 or duration_minutes > MAX_INTERVAL_MINUTES:
            continue
        if delta_pct < 0:
            continue
        intervals.append({
            "t0": prev["timestamp"],
            "t1": cur["timestamp"],
            "delta_pct": delta_pct,
            "duration_minutes": duration_minutes,
        })
    return intervals


def attribute_interval(interval, token_samples):
    """Return a clean burn sample if exactly one model generated tokens
    inside (t0, t1] - mixed intervals would force a guess about per-token
    weights, which is exactly what this measurement exists to replace."""
    by_model = {}
    for ts, tokens, model in token_samples:
        if not (interval["t0"] < ts <= interval["t1"]) or tokens <= 0:
            continue
        short = normalize_model_id(model)
        if short is None:
            continue
        by_model[short] = by_model.get(short, 0) + tokens
    if len(by_model) != 1:
        return None
    model, tokens = next(iter(by_model.items()))
    return {
        "model": model,
        "delta_pct": interval["delta_pct"],
        "duration_minutes": interval["duration_minutes"],
        "tokens": tokens,
        "t0": interval["t0"],
        "t1": interval["t1"],
    }


def compute_averages(samples):
    """Duration-weighted average burn rate per model: sum(delta) / sum(minutes).
    Robust to the ~1% granularity of used_percentage - individual samples are
    coarse, but the aggregate converges."""
    totals = {}
    for s in samples:
        delta, minutes = totals.get(s["model"], (0.0, 0.0))
        totals[s["model"]] = (delta + s["delta_pct"], minutes + s["duration_minutes"])
    return {
        model: {"rate": delta / minutes, "minutes": minutes}
        for model, (delta, minutes) in totals.items()
        if minutes > 0
    }


def eligible_models(averages):
    return {m: a for m, a in averages.items() if a["minutes"] >= MIN_ELIGIBLE_MINUTES}


def detect_current_model(token_samples, now, lookback_seconds=CURRENT_MODEL_LOOKBACK_SECONDS):
    by_model = {}
    for ts, tokens, model in token_samples:
        if now - ts > lookback_seconds or tokens <= 0:
            continue
        short = normalize_model_id(model)
        if short is not None:
            by_model[short] = by_model.get(short, 0) + tokens
    if not by_model:
        return None
    return max(by_model, key=by_model.get)
