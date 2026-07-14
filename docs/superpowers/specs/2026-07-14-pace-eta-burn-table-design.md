# Pace ETA + Model Burn Table

2026-07-14

## Problem

The pace marker (`monitor.py` render) shows a BELOW/AT/ABOVE verdict but not
a concrete "so what happens if this continues" projection. The model burn
line is a single joined string that gets harder to scan as more models
accumulate data.

## Changes

### 1. Pace line gets a projection

New pure function in `pace.py`:

```python
def project_landing(used_pct, current_rate, now, resets_at):
    """Where the current rate lands if it holds steady.
    Returns {"kind": "exhaust", "at": <epoch seconds>} if used_pct hits
    100 before resets_at, else {"kind": "land", "pct": <float 0-100>}.
    """
```

Logic: `remaining_minutes = (resets_at - now) / 60`; if `current_rate <= 0`,
always "land" at `used_pct` (never exhausts). Otherwise
`minutes_to_100 = (100 - used_pct) / current_rate`. If
`minutes_to_100 <= remaining_minutes`: `{"kind": "exhaust", "at": now + minutes_to_100 * 60}`.
Else: `{"kind": "land", "pct": clamp(used_pct + current_rate * remaining_minutes, 0, 100)}`.

New formatter `format_clock(epoch_seconds)` -> local 12-hour time, no
leading zero, lowercase am/pm (`"7:20pm"`, `"12:05am"`), matching the
existing terse style of `format_duration`.

`monitor.py`'s `render()` appends the projection right after the pace
marker, before the existing dim `Resets in:` suffix:

```
Pace: ABOVE (ease off)   finish by 7:20pm   Resets in: 2h 15m
Pace: BELOW (use more)   lands at 82%       Resets in: 2h 15m
Pace: AT (right on pace)   finish by 8:58pm   Resets in: 2h 15m
```

Text is `"finish by {clock}"` for `exhaust`, `"lands at {pct:.0f}%"` for
`land`. Rendered in the same pace color as the marker (`pace_color(pace)`),
not dim — it's part of the verdict, not metadata.

This computation runs unconditionally in `render()` (cheap, pure, no I/O),
regardless of pace value — AT included.

### 2. Model burn becomes a table, always visible

New pure function in `model_burn.py`:

```python
def burn_rows(rates):
    """rates: output of apply_estimates(averages).
    Returns [(model, rate_str, measured_str), ...] sorted by rate desc.
    rate_str: "0.70%/min" if measured, "~1.40%/min" if estimated (~ prefix).
    measured_str: "{:.0f}m" of accumulated clean minutes, always numeric
    (0m for a model with zero measured minutes, estimated or not).
    """
```

`monitor.py` replaces the joined `burn_text` string with a borderless
`rich.Table` (no box, dim header row: `MODEL  RATE  MEASURED`), built from
`burn_rows(rates)`. Column alignment: MODEL left, RATE right, MEASURED
right.

Visibility change: the whole model-burn block currently gates on
`pace != "AT"`. Split that gate:
- The **table** renders whenever `rates` is non-empty, at every pace
  (including AT). It's reference data, not a suggestion.
- The two **SUGGEST** lines (`suggest(...)` and
  `suggest_hot_session_action(...)`) stay gated to `pace != "AT"`, unchanged
  from today.

When `rates` is empty (`model_stats` present but no eligible/estimated
model yet), nothing renders — same as today's "collecting data" silence
for the table specifically (the dim "collecting data" SUGGEST line still
only shows when pace != AT, per existing behavior).

## Non-goals

- No change to how `current_rate`, `ideal_rate`, or `apply_estimates` are
  computed — this only adds a projection and a presentation layer on top
  of existing numbers.
- No change to the suggestion logic (`suggest`, `suggest_hot_session_action`).
- No persistence changes — nothing new is written to disk.

## Testing

`tests/test_pace.py`: `project_landing` — exhausts before reset (ABOVE
case), lands after reset (BELOW case), zero rate (always lands at
used_pct), negative rate (treated as zero/lands), already-at-100 (exhaust
at `now`), exact-boundary (`minutes_to_100 == remaining_minutes`, exhaust
not land). `format_clock` — am/pm, no leading zero, midnight/noon
boundaries.

`tests/test_model_burn.py`: `burn_rows` — sorts by rate descending,
`~` prefix only on estimated rows, `measured_str` is always numeric
(`"0m"` for unmeasured), empty input returns `[]`.

## Docs

README gets the updated pace-line example and the new table format in the
same change (per standing instruction: docs ship with the code, not as a
follow-up).
