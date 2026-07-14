# Pace ETA + Model Burn Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "finish by HH:MM" / "lands at NN%" projection next to the pace marker, and turn the single-line model burn readout into an always-visible, borderless three-column table (model, rate, measured minutes).

**Architecture:** Two new pure functions (`pace.project_landing`, `pace.format_clock`, `model_burn.burn_rows`) carry all the new math/formatting and get unit tests with zero I/O. `monitor.py`'s `render()` wires those functions into the existing `pace_line` Text and replaces the joined burn string with a `rich.Table`, splitting the old single `pace != "AT"` gate: the table now renders whenever there are rates to show (any pace), while the two `SUGGEST` lines stay gated to `pace != "AT"`.

**Tech Stack:** Python 3, `rich` (Console/Panel/Group/Text/Table), `pytest`.

## Global Constraints

- No changes to `compute_current_rate`, `compute_ideal_rate`, `apply_estimates`, `suggest`, or `suggest_hot_session_action` — this plan only adds a projection and a presentation layer.
- No new persistence — nothing new written to disk.
- Follow the existing terse formatting style (`format_duration`'s `"2h 43m"` / `"9m"` style) for anything new.
- README must be updated in the same change (per project convention: docs ship with the code).

---

### Task 1: `project_landing` and `format_clock` in `pace.py`

**Files:**
- Modify: `pace.py` (append two functions at end of file)
- Test: `tests/test_pace.py` (append tests at end of file)

**Interfaces:**
- Produces: `project_landing(used_pct, current_rate, now, resets_at) -> dict` — either `{"kind": "exhaust", "at": <epoch seconds float>}` or `{"kind": "land", "pct": <float, clamped 0-100>}`.
- Produces: `format_clock(epoch_seconds) -> str` — local 12-hour clock, no leading zero, lowercase am/pm, e.g. `"7:20pm"`, `"12:05am"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pace.py`:

```python
from pace import project_landing, format_clock

def test_project_landing_exhausts_before_reset():
    # 50% used, 1.0%/min, 60 min remaining -> exhausts at 50 min in
    result = project_landing(used_pct=50, current_rate=1.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 4000.0}

def test_project_landing_lands_after_reset():
    # 50% used, 0.5%/min, 60 min remaining -> only reaches 80% by reset
    result = project_landing(used_pct=50, current_rate=0.5, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 80.0}

def test_project_landing_zero_rate_lands_at_used_pct():
    result = project_landing(used_pct=42.0, current_rate=0.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 42.0}

def test_project_landing_negative_rate_lands_at_used_pct():
    result = project_landing(used_pct=42.0, current_rate=-0.3, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "land", "pct": 42.0}

def test_project_landing_already_at_100_exhausts_now():
    result = project_landing(used_pct=100, current_rate=0.5, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 1000.0}

def test_project_landing_exact_boundary_is_exhaust_not_land():
    # minutes_to_100 (60) == remaining_minutes (60) exactly -> exhaust wins
    result = project_landing(used_pct=40, current_rate=1.0, now=1000, resets_at=1000 + 3600)
    assert result == {"kind": "exhaust", "at": 4600.0}


def _local_ts(hour, minute):
    # Builds a timestamp for today at the given local hour/minute, so the
    # test is timezone-agnostic - it works no matter what TZ the machine
    # running pytest is set to.
    now = time.localtime()
    t = time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1))
    return time.mktime(t)

def test_format_clock_pm_no_leading_zero():
    assert format_clock(_local_ts(19, 20)) == "7:20pm"

def test_format_clock_am_no_leading_zero():
    assert format_clock(_local_ts(7, 5)) == "7:05am"

def test_format_clock_midnight_is_12am():
    assert format_clock(_local_ts(0, 5)) == "12:05am"

def test_format_clock_noon_is_12pm():
    assert format_clock(_local_ts(12, 0)) == "12:00pm"
```

Also add `import time` to the top of `tests/test_pace.py` (it currently only imports `sys, os`):

```python
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pace.py -v -k "project_landing or format_clock"`
Expected: FAIL with `ImportError: cannot import name 'project_landing'` (or similar — the functions don't exist yet).

- [ ] **Step 3: Implement `project_landing` and `format_clock`**

Append to `pace.py`:

```python
def project_landing(used_pct, current_rate, now, resets_at):
    """Where the current rate lands if it holds steady. Either the window
    exhausts (hits 100%) before it resets, or it doesn't and there's
    allowance left unused at reset time."""
    remaining_minutes = (resets_at - now) / 60
    if current_rate <= 0:
        return {"kind": "land", "pct": max(0.0, min(100.0, used_pct))}
    minutes_to_100 = (100 - used_pct) / current_rate
    if minutes_to_100 <= remaining_minutes:
        return {"kind": "exhaust", "at": now + minutes_to_100 * 60}
    pct = used_pct + current_rate * remaining_minutes
    return {"kind": "land", "pct": max(0.0, min(100.0, pct))}


def format_clock(epoch_seconds):
    return time.strftime("%-I:%M%p", time.localtime(epoch_seconds)).lower()
```

Add `import time` to the top of `pace.py` if not already present (`pace.py` currently has no imports at all — add it as the first line of the file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pace.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add pace.py tests/test_pace.py
git commit -m "feat: add pace projection and clock formatting"
```

---

### Task 2: `burn_rows` in `model_burn.py`

**Files:**
- Modify: `model_burn.py` (append function at end of file)
- Test: `tests/test_model_burn.py` (append tests at end of file)

**Interfaces:**
- Consumes: the `rates` dict shape produced by `apply_estimates` (already defined in `model_burn.py`): `{model: {"rate": float, "minutes": float, "estimated": bool}}`.
- Produces: `burn_rows(rates) -> list[tuple[str, str, str]]` — `(model, rate_str, measured_str)` sorted by rate descending. `rate_str` is `"0.70%/min"` for measured rows, `"~1.40%/min"` (tilde prefix) for estimated rows. `measured_str` is always `"{:.0f}m"` of accumulated minutes (e.g. `"0m"` for an estimated/unmeasured model).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_model_burn.py`:

```python
from model_burn import burn_rows

def test_burn_rows_sorts_by_rate_descending_and_marks_estimates():
    rates = {
        "fable": {"rate": 1.4, "minutes": 0.0, "estimated": True},
        "opus": {"rate": 0.7, "minutes": 84.0, "estimated": False},
        "sonnet": {"rate": 0.42, "minutes": 31.0, "estimated": False},
        "haiku": {"rate": 0.14, "minutes": 0.0, "estimated": True},
    }
    assert burn_rows(rates) == [
        ("fable", "~1.40%/min", "0m"),
        ("opus", "0.70%/min", "84m"),
        ("sonnet", "0.42%/min", "31m"),
        ("haiku", "~0.14%/min", "0m"),
    ]

def test_burn_rows_measured_is_numeric_even_when_zero():
    rates = {"opus": {"rate": 0.7, "minutes": 0.0, "estimated": False}}
    assert burn_rows(rates) == [("opus", "0.70%/min", "0m")]

def test_burn_rows_empty_input_returns_empty_list():
    assert burn_rows({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_burn.py -v -k burn_rows`
Expected: FAIL with `ImportError: cannot import name 'burn_rows'`.

- [ ] **Step 3: Implement `burn_rows`**

Append to `model_burn.py`:

```python
def burn_rows(rates):
    """Turn apply_estimates() output into sorted (model, rate_str,
    measured_str) rows ready to hand to a table renderer."""
    rows = []
    for model in sorted(rates, key=lambda m: rates[m]["rate"], reverse=True):
        a = rates[model]
        prefix = "~" if a["estimated"] else ""
        rate_str = "{}{:.2f}%/min".format(prefix, a["rate"])
        measured_str = "{:.0f}m".format(a["minutes"])
        rows.append((model, rate_str, measured_str))
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_model_burn.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add model_burn.py tests/test_model_burn.py
git commit -m "feat: add burn_rows table formatting for model burn stats"
```

---

### Task 3: Wire the pace-line projection into `monitor.py`

**Files:**
- Modify: `monitor.py:9-16` (import block), `monitor.py` (the `pace_line` construction inside `render()`)
- Test: `tests/test_monitor.py` (append tests at end of file)

**Interfaces:**
- Consumes: `project_landing(used_pct, current_rate, now, resets_at)` and `format_clock(epoch_seconds)` from Task 1.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_monitor.py`:

```python
def test_render_pace_line_shows_finish_by_when_projection_exhausts():
    now = time.time()
    # used 50%, rate ramps 40->50 over 10 min = 1.0%/min, ideal = 50/100 = 0.5%/min
    # -> ABOVE pace, and exhausts before the 100-minute reset
    state = {"used_percentage": 50, "resets_at": now + 6000}
    history = [{"timestamp": now - 600, "used_percentage": 40, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], None, None)
    text = _panel_text(panel)
    assert "Pace: ABOVE" in text
    assert "finish by " in text

def test_render_pace_line_shows_lands_at_when_projection_undershoots():
    now = time.time()
    # used 10%, rate ramps 5->10 over 10 min = 0.5%/min, ideal = 90/100 = 0.9%/min
    # -> BELOW pace, and never reaches 100% before the 100-minute reset
    state = {"used_percentage": 10, "resets_at": now + 6000}
    history = [{"timestamp": now - 600, "used_percentage": 5, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], None, None)
    text = _panel_text(panel)
    assert "Pace: BELOW" in text
    assert "lands at " in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_monitor.py -v -k "finish_by or lands_at"`
Expected: FAIL — `"finish by "` / `"lands at "` not present in the rendered text (current `pace_line` doesn't include a projection yet).

- [ ] **Step 3: Wire the projection into `render()`**

In `monitor.py`, update the import from `pace` (currently lines 9-16):

```python
from pace import (
    compute_elapsed_percentage,
    compute_ideal_rate,
    compute_current_rate,
    compute_pace,
    is_stale,
    format_duration,
    project_landing,
    format_clock,
)
```

Then update the `pace_line` construction inside `render()` (currently):

```python
    pace_line = Text(
        "Pace: {} ({})".format(pace, PACE_HINTS[pace]),
        style="bold {}".format(pace_color(pace)),
    )
    pace_line.append("   Resets in: {}".format(format_duration(resets_at - now)), style="dim")
```

to:

```python
    pace_line = Text(
        "Pace: {} ({})".format(pace, PACE_HINTS[pace]),
        style="bold {}".format(pace_color(pace)),
    )
    landing = project_landing(used_pct, info["current_rate"], now, resets_at)
    if landing["kind"] == "exhaust":
        projection_text = "   finish by {}".format(format_clock(landing["at"]))
    else:
        projection_text = "   lands at {:.0f}%".format(landing["pct"])
    pace_line.append(projection_text, style="bold {}".format(pace_color(pace)))
    pace_line.append("   Resets in: {}".format(format_duration(resets_at - now)), style="dim")
```

(The `[STALE]` append that follows stays exactly as-is.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_monitor.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add monitor.py tests/test_monitor.py
git commit -m "feat: show finish-by/lands-at projection next to the pace marker"
```

---

### Task 4: Replace the model-burn line with a table, decouple its visibility from `SUGGEST`

**Files:**
- Modify: `monitor.py` (import block, and the model-stats block inside `render()`)
- Test: `tests/test_monitor.py` (rewrite `_panel_text` helper, update/add tests)

**Interfaces:**
- Consumes: `burn_rows(rates)` from Task 2.
- Note: `_panel_text`'s current implementation (`getattr(r, "plain", "")` over `group.renderables`) silently returns `""` for any renderable without a `.plain` attribute — a `rich.table.Table` has no `.plain`, so table content would be invisible to existing tests. It must be replaced with a real Console-capture helper before table content can be asserted on.

- [ ] **Step 1: Write the failing tests**

First, replace the `_panel_text` helper near the top of `tests/test_monitor.py`:

```python
import io
from rich.console import Console as _CaptureConsole

def _panel_text(panel):
    console = _CaptureConsole(file=io.StringIO(), width=100, color_system=None)
    console.print(panel)
    return console.file.getvalue()
```

(Remove the old `_panel_text` that joined `.plain` attributes — the `import io` and `_CaptureConsole` import go at the top of the file alongside the existing `import sys, os, time`.)

Then update `test_render_shows_nothing_from_model_burn_at_at_pace` (it currently asserts `"Model burn" not in text` — that was the *old* gate; the table is now always shown when rates exist, so at AT pace the table should show but SUGGEST should not):

```python
def test_render_shows_nothing_from_model_burn_at_at_pace():
    now = time.time()
    state = {"used_percentage": 50, "resets_at": now + 6000}
    history = [{"timestamp": now - 600, "used_percentage": 45, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], _model_stats(), None)
    text = _panel_text(panel)
    assert "Pace: AT" in text
    assert "SUGGEST" not in text
    assert "Model burn" in text
    assert "opus" in text
```

Then append a new test asserting the table's three columns and the estimate marker:

```python
def test_render_burn_table_has_columns_and_marks_estimates():
    now = time.time()
    state = {"used_percentage": 50, "resets_at": now + 6000}
    history = [{"timestamp": now - 600, "used_percentage": 45, "resets_at": now + 6000}]
    panel = render(state, history, None, None, [], _model_stats(), None)
    text = _panel_text(panel)
    assert "MODEL" in text
    assert "RATE" in text
    assert "MEASURED" in text
    assert "opus" in text and "0.50%/min" in text and "60m" in text
    assert "~" in text  # sonnet/haiku/fable are estimated from the opus anchor
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_monitor.py -v`
Expected: `test_render_shows_nothing_from_model_burn_at_at_pace` FAILs on `assert "Model burn" in text` (old code still gates the whole block on `pace != "AT"`); `test_render_burn_table_has_columns_and_marks_estimates` FAILs the same way. (The pace-line tests from Task 3 still pass.)

- [ ] **Step 3: Replace the burn line with a table and split the visibility gate**

In `monitor.py`, update the import from `model_burn` (currently):

```python
from model_burn import gather_model_stats, suggest, apply_estimates, heaviest_session, suggest_hot_session_action
```

to:

```python
from model_burn import gather_model_stats, suggest, apply_estimates, burn_rows, heaviest_session, suggest_hot_session_action
```

Add `Table` to the `rich` imports (currently `from rich.console import Console, Group`, `from rich.live import Live`, `from rich.panel import Panel`, `from rich.text import Text`):

```python
from rich.table import Table
```

Then replace the entire model-stats block inside `render()` (currently):

```python
    # Model burn/suggestion is only useful when there's a pace problem to
    # act on - at AT pace there's nothing to suggest, so show nothing.
    if model_stats is not None and pace != "AT":
        rates = apply_estimates(model_stats["averages"])
        suggest_prefix = "\n"  # keep panel spacing when there is no burn line yet
        if rates:
            by_rate = sorted(rates.items(), key=lambda kv: kv[1]["rate"], reverse=True)
            burn_text = "Model burn: " + "   ".join(
                "{} {:.2f}%/min ({})".format(
                    m, a["rate"], "est" if a["estimated"] else "{:.0f}m".format(a["minutes"])
                )
                for m, a in by_rate
            )
            lines.append(Text("\n" + burn_text, style="bold", no_wrap=True, overflow="ellipsis"))
            suggest_prefix = ""
        suggestion = suggest(
            pace, info["ideal_rate"], info["current_rate"], used_pct,
            (resets_at - now) / 60, model_stats["current_model"], rates,
        )
        if suggestion == "collecting data":
            suggestion_style = "dim"
        else:
            suggestion_style = "bold {}".format(pace_color(pace))
        lines.append(Text("{}SUGGEST: {}".format(suggest_prefix, suggestion),
                          style=suggestion_style))

        hot_suggestion = suggest_hot_session_action(pace, info["ideal_rate"], hot_session, rates)
        if hot_suggestion:
            lines.append(Text("SUGGEST: {}".format(hot_suggestion),
                              style="bold {}".format(pace_color(pace))))
```

with:

```python
    # The burn table is reference data, useful at any pace - it renders
    # whenever there are rates to show. The suggestions are only useful when
    # there's a pace problem to act on, so they stay gated to non-AT pace.
    if model_stats is not None:
        rates = apply_estimates(model_stats["averages"])
        suggest_prefix = "\n"  # keep panel spacing when there is no table above

        if rates:
            lines.append(Text("\nModel burn:", style="bold"))
            table = Table(show_header=True, header_style="dim", box=None, pad_edge=False)
            table.add_column("MODEL")
            table.add_column("RATE", justify="right")
            table.add_column("MEASURED", justify="right")
            for model, rate_str, measured_str in burn_rows(rates):
                table.add_row(model, rate_str, measured_str)
            lines.append(table)
            suggest_prefix = ""

        if pace != "AT":
            suggestion = suggest(
                pace, info["ideal_rate"], info["current_rate"], used_pct,
                (resets_at - now) / 60, model_stats["current_model"], rates,
            )
            if suggestion == "collecting data":
                suggestion_style = "dim"
            else:
                suggestion_style = "bold {}".format(pace_color(pace))
            lines.append(Text("{}SUGGEST: {}".format(suggest_prefix, suggestion),
                              style=suggestion_style))

            hot_suggestion = suggest_hot_session_action(pace, info["ideal_rate"], hot_session, rates)
            if hot_suggestion:
                lines.append(Text("SUGGEST: {}".format(hot_suggestion),
                                  style="bold {}".format(pace_color(pace))))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_monitor.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: PASS, all tests across `tests/` (pace, model_burn, monitor, and everything else — no regressions from the `_panel_text` helper rewrite or the import changes).

- [ ] **Step 6: Commit**

```bash
git add monitor.py tests/test_monitor.py
git commit -m "feat: render model burn as a table, decouple its visibility from suggestions"
```

---

### Task 5: Update README and do a manual visual check

**Files:**
- Modify: `README.md` (the pace-badge bullet and the per-model-burn bullet, near lines 15 and 22)

- [ ] **Step 1: Update the pace-badge bullet**

In `README.md`, find:

```markdown
- A **pace badge** (`ABOVE` / `AT` / `BELOW`) that tells you plainly whether to **ease off**, **use more**, or you're **right on pace**
```

Replace with:

```markdown
- A **pace badge** (`ABOVE` / `AT` / `BELOW`) that tells you plainly whether to **ease off**, **use more**, or you're **right on pace** — right next to it, a live projection: `finish by 7:20pm` if your current rate would exhaust the window before it resets, or `lands at 82%` if it wouldn't
```

- [ ] **Step 2: Update the per-model-burn bullet**

In `README.md`, find (the paragraph starting with `- **Per-model burn rates**`):

```markdown
- **Per-model burn rates**: measures how fast each Claude model (Haiku, Sonnet, Opus, Fable) empirically burns the 5h limit in %/min, and a **model suggestion** that only appears when there's actually something to act on — `one more opus session` when you're under pace, `switch to fable`/`ease off` when you're over. At `AT` pace the whole section is hidden: there's nothing to suggest when you're already right on track. Models you haven't measured yet get an estimate scaled from your best-measured model by Anthropic's API price ratio (Haiku : Sonnet : Opus : Fable = 1 : 3 : 5 : 10), shown as `(est)`; ~10 minutes of single-model usage with the monitor open replaces an estimate with your real measured rate.
```

Replace with:

```markdown
- **Per-model burn rates**, shown as a table (model, rate, measured minutes): measures how fast each Claude model (Haiku, Sonnet, Opus, Fable) empirically burns the 5h limit in %/min. The table is reference data and stays visible at every pace, including `AT`. A **model suggestion** appears below it only when there's actually something to act on — `one more opus session` when you're under pace, `switch to fable`/`ease off` when you're over; at `AT` pace there's nothing to suggest, so the suggestion lines (not the table) are hidden. Models you haven't measured yet get an estimate scaled from your best-measured model by Anthropic's API price ratio (Haiku : Sonnet : Opus : Fable = 1 : 3 : 5 : 10), shown with a `~` prefix on the rate (e.g. `~1.40%/min`); ~10 minutes of single-model usage with the monitor open replaces an estimate with your real measured rate.
```

- [ ] **Step 3: Manually verify the rendered output**

Run: `python3 -c "
import time
from monitor import render
now = time.time()
state = {'used_percentage': 62, 'resets_at': now + 3000}
history = [{'timestamp': now - 600, 'used_percentage': 50, 'resets_at': now + 3000}]
model_stats = {'averages': {'opus': {'rate': 0.5, 'minutes': 84.0}, 'sonnet': {'rate': 0.2, 'minutes': 31.0}}, 'current_model': 'opus'}
from rich.console import Console
Console().print(render(state, history, None, None, [], model_stats, None))
"`

Expected: a panel showing `Pace: ABOVE` (or whichever verdict the numbers land on) with a `finish by HH:MMam/pm` or `lands at NN%` projection right next to it, and a `Model burn:` table below with `MODEL / RATE / MEASURED` columns, `opus` and `sonnet` measured, `haiku`/`fable` shown with a `~` estimate prefix. Confirm visually that columns are aligned and nothing is cut off.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README for pace projection and model burn table"
```
