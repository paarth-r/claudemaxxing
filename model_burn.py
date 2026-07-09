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


def _stay(current_model, eligible, ideal_rate):
    if current_model:
        return "stay on {}".format(current_model)
    closest = min(eligible, key=lambda m: abs(eligible[m]["rate"] - ideal_rate))
    return "stay on {}".format(closest)


def suggest(pace, ideal_rate, current_rate, used_pct, remaining_minutes, current_model, averages):
    """Turn per-model burn rates into an action. 'Heavier' means a higher
    measured burn rate - that is what heaviness means for the limit, and it
    needs no hardcoded ladder for unknown model ids."""
    eligible = eligible_models(averages)
    if not eligible:
        return "collecting data"
    by_rate_desc = sorted(eligible, key=lambda m: eligible[m]["rate"], reverse=True)

    if pace == "BELOW":
        surplus_pct = (100.0 - used_pct) - current_rate * remaining_minutes
        for m in by_rate_desc:
            if surplus_pct >= eligible[m]["rate"] * NOMINAL_SESSION_MINUTES:
                return "one more {} session".format(m)
        faster = [
            m for m in by_rate_desc
            if m != current_model
            and eligible[m]["rate"] > current_rate
            and abs(eligible[m]["rate"] - ideal_rate) < abs(current_rate - ideal_rate)
        ]
        if faster:
            best = min(faster, key=lambda m: abs(eligible[m]["rate"] - ideal_rate))
            return "switch to {}".format(best)
        return _stay(current_model, eligible, ideal_rate)

    if pace == "ABOVE":
        fits = [m for m in by_rate_desc if eligible[m]["rate"] <= ideal_rate]
        if fits:
            if fits[0] == current_model:
                return "stay on {}".format(current_model)
            return "switch to {}".format(fits[0])
        lightest = by_rate_desc[-1]
        return "ease off - even {} overshoots".format(lightest)

    return _stay(current_model, eligible, ideal_rate)


def gather_model_stats(history, now, burn_path=MODEL_BURN_PATH,
                       cursor_path=MODEL_BURN_CURSOR_PATH,
                       token_samples_fn=recent_token_samples):
    """One monitor tick: turn newly-completed usage intervals into permanent
    clean burn samples, advance the cursor (mixed/zero intervals are consumed
    too - never rescanned), and return fresh averages + the current model."""
    cursor = read_state(path=cursor_path) or {}
    intervals = build_intervals(history, cursor.get("last_processed", 0))

    cutoff = now - CURRENT_MODEL_LOOKBACK_SECONDS
    if intervals:
        cutoff = min(cutoff, intervals[0]["t0"])
    token_samples = token_samples_fn(cutoff=cutoff)

    # (t0, t1) identity guards against double-counting when the cursor is
    # lost or corrupt and old intervals get re-mined - the burn file is read
    # every tick for the averages anyway, so this costs nothing extra.
    stored = read_history(path=burn_path)
    seen = {(s.get("t0"), s.get("t1")) for s in stored}
    for interval in intervals:
        if (interval["t0"], interval["t1"]) in seen:
            continue
        clean = attribute_interval(interval, token_samples)
        if clean is not None:
            append_history(clean, path=burn_path)
            stored.append(clean)
    if intervals:
        write_state({"last_processed": max(i["t1"] for i in intervals)}, path=cursor_path)

    return {
        "averages": compute_averages(stored),
        "current_model": detect_current_model(token_samples, now),
    }
