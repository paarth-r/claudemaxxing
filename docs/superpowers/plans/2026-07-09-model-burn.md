# Per-Model Burn Rate & Model Suggestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure each Claude model's empirical burn rate against the 5h usage limit (usage%/min) and render an actionable suggestion ("one more opus session", "switch to fable") in the claudemaxxing dashboard.

**Architecture:** The statusline hook already appends usage% change events to `history.jsonl`. A new `model_burn.py` module, driven from `monitor.py`'s once-a-minute loop, pairs consecutive history samples into intervals, attributes each interval's usage% delta to a model via transcript token activity (clean single-model intervals only), persists samples permanently, and computes duration-weighted per-model averages plus a suggestion.

**Tech Stack:** Python 3, `rich` (already a dependency), pytest for tests. No new dependencies.

## Global Constraints

- No emojis anywhere (UI, commits, docs) — project and user rule.
- Statusline hook (`usage_statusline.py`) must NOT be touched — it must stay fast.
- All new persistent files live in `~/.claude/usage-monitor/` alongside existing state.
- Token counting matches `stats.py`: input + output + cache_creation, excluding cache_read.
- Every storage/IO helper reuses `state_io.py`'s generic path-parameterized functions.
- Run tests from the repo root: `python3 -m pytest tests/ -q`.
- Spec: `docs/superpowers/specs/2026-07-09-model-burn-design.md`.

---

### Task 1: Model-aware token samples in stats.py

`recent_token_samples` currently returns `(timestamp, tokens)` tuples. Extend it to `(timestamp, tokens, model)` triples so downstream code can bucket by model, and adapt the one existing consumer.

**Files:**
- Modify: `stats.py:66-116` (`recent_token_samples`, `tokens_per_minute`)
- Test: `tests/test_stats.py`

**Interfaces:**
- Produces: `recent_token_samples(cutoff, projects_dir=..., tail_bytes=..., max_tail_bytes=...) -> list[(float, int, str|None)]` — third element is the raw `message.model` string or None.
- `compute_tokens_per_minute` and `tokens_per_minute` keep their existing signatures and return types.

- [ ] **Step 1: Update existing tests to the 3-tuple shape and add a model-extraction test**

In `tests/test_stats.py`, change the helper to accept a model and update the two `recent_token_samples` tests:

```python
def _write_jsonl_line(f, timestamp_epoch, usage, model=None):
    import datetime
    ts_str = datetime.datetime.utcfromtimestamp(timestamp_epoch).isoformat() + "Z"
    message = {"role": "assistant", "usage": usage}
    if model is not None:
        message["model"] = model
    f.write(json.dumps({"timestamp": ts_str, "message": message}) + "\n")
```

In `test_recent_token_samples_finds_data_beyond_a_small_initial_tail_guess`, change the unpacking line:

```python
    buried_message_tokens = [t for ts, t, _model in recent if t == 20]
```

In `test_recent_token_samples_excludes_cache_read_tokens`, change the assertion:

```python
    assert samples == [(samples[0][0], 10, None)]  # 2+3+5, cache_read excluded
```

Add a new test at the end of the file:

```python
def test_recent_token_samples_includes_model(tmp_path):
    path = tmp_path / "session.jsonl"
    now = time.time()
    with open(path, "w") as f:
        _write_jsonl_line(f, now - 10, {"input_tokens": 2, "output_tokens": 3}, model="claude-fable-5")
    samples = recent_token_samples(cutoff=now - 300, projects_dir=str(tmp_path))
    assert samples == [(samples[0][0], 5, "claude-fable-5")]
```

- [ ] **Step 2: Run tests to verify the new/changed ones fail**

Run: `python3 -m pytest tests/test_stats.py -q`
Expected: FAIL — 2-tuples returned where 3-tuples expected (ValueError on unpack / assertion mismatch).

- [ ] **Step 3: Implement**

In `stats.py`, in `recent_token_samples`, change the append line (currently `samples.append((ts, total_tokens))`):

```python
                    samples.append((ts, total_tokens, message.get("model")))
```

And in `tokens_per_minute`, adapt the consumer:

```python
def tokens_per_minute(window_seconds=300):
    now = time.time()
    samples = recent_token_samples(cutoff=now - window_seconds)
    pairs = [(ts, tokens) for ts, tokens, _model in samples]
    return compute_tokens_per_minute(pairs, now=now, window_seconds=window_seconds)
```

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add stats.py tests/test_stats.py
git commit -m "Include model id in transcript token samples"
```

---

### Task 2: model_burn.py — model normalization and interval building

**Files:**
- Create: `model_burn.py`
- Test: `tests/test_model_burn.py`

**Interfaces:**
- Produces: `normalize_model_id(model_id) -> str|None` — `"claude-fable-5" -> "fable"`, unknown ids pass through raw, None/empty -> None.
- Produces: `build_intervals(history, last_processed) -> list[dict]` — dicts with keys `t0`, `t1`, `delta_pct`, `duration_minutes`. `history` is the list of `{"timestamp", "used_percentage", "resets_at"}` dicts from `state_io.read_history()`, chronological.
- Produces: module constants `MODEL_BURN_PATH`, `MODEL_BURN_CURSOR_PATH`, `MIN_ELIGIBLE_MINUTES = 10.0`, `NOMINAL_SESSION_MINUTES = 30.0`, `MAX_INTERVAL_MINUTES = 20.0`, `CURRENT_MODEL_LOOKBACK_SECONDS = 600`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_model_burn.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'model_burn'`.

- [ ] **Step 3: Implement**

Create `model_burn.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "Add model id normalization and usage interval building"
```

---

### Task 3: Clean-interval attribution

**Files:**
- Modify: `model_burn.py` (append function)
- Test: `tests/test_model_burn.py`

**Interfaces:**
- Consumes: `normalize_model_id` from Task 2; token samples are the `(timestamp, tokens, model)` triples from Task 1.
- Produces: `attribute_interval(interval, token_samples) -> dict|None` — a clean burn sample `{"model", "delta_pct", "duration_minutes", "tokens", "t0", "t1"}` if exactly one model generated tokens in `(t0, t1]`, else None.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_model_burn.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: FAIL with ImportError (`attribute_interval` not defined).

- [ ] **Step 3: Implement**

Append to `model_burn.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "Attribute usage deltas to single-model clean intervals"
```

---

### Task 4: Averaging, eligibility, current-model detection

**Files:**
- Modify: `model_burn.py` (append functions)
- Test: `tests/test_model_burn.py`

**Interfaces:**
- Produces: `compute_averages(samples) -> {model: {"rate": float, "minutes": float}}` — duration-weighted; `samples` are the stored burn-sample dicts.
- Produces: `eligible_models(averages) -> dict` — subset with `minutes >= MIN_ELIGIBLE_MINUTES`.
- Produces: `detect_current_model(token_samples, now, lookback_seconds=600) -> str|None` — normalized short name of the model with the most tokens in the lookback, None if nothing generated.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_model_burn.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `model_burn.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "Add duration-weighted averages, eligibility, current-model detection"
```

---

### Task 5: Suggestion engine

**Files:**
- Modify: `model_burn.py` (append functions)
- Test: `tests/test_model_burn.py`

**Interfaces:**
- Consumes: `eligible_models` from Task 4; `pace` strings from `pace.compute_pace` ("BELOW"/"AT"/"ABOVE").
- Produces: `suggest(pace, ideal_rate, current_rate, used_pct, remaining_minutes, current_model, averages) -> str` — one of: `"collecting data"`, `"one more {m} session"`, `"switch to {m}"`, `"stay on {m}"`, `"ease off - even {m} overshoots"`.
- "Heavier" is defined empirically as a higher measured burn rate — that is literally what heaviness means for the limit, and it needs no hardcoded ladder for unknown model ids.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_model_burn.py`:

```python
from model_burn import suggest

AVGS = {
    "fable":  {"rate": 0.9, "minutes": 60.0},
    "opus":   {"rate": 0.5, "minutes": 60.0},
    "sonnet": {"rate": 0.2, "minutes": 60.0},
    "haiku":  {"rate": 0.05, "minutes": 60.0},
}

def test_suggest_collecting_data_when_nothing_eligible():
    sparse = {"fable": {"rate": 0.9, "minutes": 2.0}}
    assert suggest("BELOW", 0.5, 0.1, 20, 120, "fable", sparse) == "collecting data"
    assert suggest("BELOW", 0.5, 0.1, 20, 120, None, {}) == "collecting data"

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
```

Note for `test_suggest_below_stays_when_already_on_the_only_candidate`: the switch-up branch requires the candidate's rate to be *closer to ideal* than the current rate AND the candidate to differ from the current model — staying put beats "switching" to the model already in use. The test pins current_model="haiku" so the only candidate is excluded.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `model_burn.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: PASS. If `test_suggest_below_stays_when_already_on_the_only_candidate` fails by returning "switch to haiku", the `m != current_model` guard in the `faster` filter is missing.

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "Add action-phrase model suggestion engine"
```

---

### Task 6: Storage driver — gather_model_stats

**Files:**
- Modify: `model_burn.py` (append function)
- Test: `tests/test_model_burn.py`

**Interfaces:**
- Consumes: `state_io.read_state/write_state/read_history/append_history` (all path-parameterized), `stats.recent_token_samples`, plus Tasks 2-4.
- Produces: `gather_model_stats(history, now, burn_path=..., cursor_path=..., token_samples_fn=recent_token_samples) -> {"averages": dict, "current_model": str|None}` — the one call `monitor.py` makes per tick. Processes any new intervals into permanent clean samples, advances the cursor, returns fresh averages and the current model.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_model_burn.py`:

```python
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

def test_gather_model_stats_empty_history(tmp_path):
    result = gather_model_stats([], now=200,
                                burn_path=str(tmp_path / "b.jsonl"),
                                cursor_path=str(tmp_path / "c.json"),
                                token_samples_fn=lambda cutoff: [])
    assert result == {"averages": {}, "current_model": None}
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_model_burn.py -q`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `model_burn.py`:

```python
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

    for interval in intervals:
        clean = attribute_interval(interval, token_samples)
        if clean is not None:
            append_history(clean, path=burn_path)
    if intervals:
        write_state({"last_processed": max(i["t1"] for i in intervals)}, path=cursor_path)

    return {
        "averages": compute_averages(read_history(path=burn_path)),
        "current_model": detect_current_model(token_samples, now),
    }
```

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "Add gather_model_stats driver with persistent samples and cursor"
```

---

### Task 7: Monitor integration and panel rendering

**Files:**
- Modify: `monitor.py` (imports, `render` signature + body, `main` loop)

**Interfaces:**
- Consumes: `gather_model_stats`, `suggest`, `MODEL_BURN_PATH` from `model_burn.py`; existing `pace_info`.
- Produces: dashboard lines like `Model burn: fable 0.90%/min (42m)   opus 0.55%/min (118m)` and `SUGGEST: one more opus session`.

- [ ] **Step 1: Add the import and render support**

In `monitor.py`, after the `heatmap` import add:

```python
from model_burn import gather_model_stats, suggest
```

Change the `render` signature:

```python
def render(state, history, last_quote, live_stats=None, window_history=None, model_stats=None):
```

Insert after the `live_stats` block (after `lines.append(Text(stats_text, style="bold"))` and before the quote block):

```python
    if model_stats is not None:
        averages = model_stats["averages"]
        suggest_prefix = "\n"  # keep panel spacing when there is no burn line yet
        if averages:
            by_rate = sorted(averages.items(), key=lambda kv: kv[1]["rate"], reverse=True)
            burn_text = "Model burn: " + "   ".join(
                "{} {:.2f}%/min ({:.0f}m)".format(m, a["rate"], a["minutes"])
                for m, a in by_rate
            )
            lines.append(Text("\n" + burn_text, style="bold"))
            suggest_prefix = ""
        suggestion = suggest(
            pace, info["ideal_rate"], info["current_rate"], used_pct,
            (resets_at - now) / 60, model_stats["current_model"], averages,
        )
        if suggestion == "collecting data":
            suggestion_style = "dim"
        else:
            suggestion_style = "bold {}".format(pace_color(pace))
        lines.append(Text("{}SUGGEST: {}".format(suggest_prefix, suggestion),
                          style=suggestion_style))
```

- [ ] **Step 2: Wire the main loop**

In `main()`, after the `live_stats = {...}` assignment add:

```python
            model_stats = None
            try:
                model_stats = gather_model_stats(history, time.time())
            except Exception:
                model_stats = None  # measurement must never take down the dashboard
```

And change the update call:

```python
            live.update(render(state, history, last_quote, live_stats, window_history, model_stats))
```

- [ ] **Step 3: Run the full suite and a smoke render**

Run: `python3 -m pytest tests/ -q`
Expected: all PASS.

Smoke-check that the module imports and renders without crashing:

Run: `python3 -c "import time, monitor; p = monitor.render({'used_percentage': 40, 'resets_at': time.time() + 9000}, [], None, {'tokens_per_minute': 100, 'active_sessions': 1}, [], {'averages': {'opus': {'rate': 0.5, 'minutes': 60.0}}, 'current_model': 'opus'}); print('render ok')"`
Expected: `render ok`

- [ ] **Step 4: Commit**

```bash
git add monitor.py
git commit -m "Render per-model burn rates and model suggestion in dashboard"
```

---

### Task 8: Docs — README and spec amendments

**Files:**
- Modify: `README.md` (feature list + "How it works")
- Modify: `docs/superpowers/specs/2026-07-09-model-burn-design.md` (two implementation-driven amendments)

- [ ] **Step 1: Amend the spec**

Two deviations discovered while planning, to record in the spec (edit the relevant sections in place):

1. In "Measurement" add a rule: intervals longer than 20 minutes are discarded. `history.jsonl` records change events, so a 1% tick after a long idle stretch spans the idle time and would dilute the measured rate.
2. In "Suggestion engine" replace the fixed heaviness ladder with: heaviness = measured burn rate, descending. Empirical rate ordering is what heaviness means for the limit and handles unknown model ids with no special casing. The ease-off message names the lightest *measured* model: `ease off - even {lightest} overshoots`.

- [ ] **Step 2: Update README**

In the "What it does" list, after the tokens/min bullet, add:

```markdown
- **Per-model burn rates**: measures how fast each Claude model (Haiku, Sonnet, Opus, Fable) empirically burns the 5h limit in %/min — learned from your real usage, not hardcoded weights — and a **model suggestion** that tells you what to actually do: `one more opus session`, `switch to fable`, `stay on sonnet`, or `ease off`. To calibrate a model quickly, run any prompt in a fresh context using only that model for ~10 minutes with the monitor open.
```

In "How it works", after the pace bullet, add:

```markdown
- Per-model burn attribution is conservative: a usage% delta only becomes a measurement when exactly one model was generating tokens during that interval (checked against your local transcripts). Mixed-model intervals and long idle gaps are discarded rather than guessed at. Samples persist forever in `~/.claude/usage-monitor/model_burn.jsonl`, so the averages keep sharpening across restarts.
```

- [ ] **Step 3: Run the full suite one last time**

Run: `python3 -m pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-07-09-model-burn-design.md
git commit -m "Document per-model burn rates and model suggestion"
```
