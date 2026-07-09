# Per-Model Burn Rate & Model Suggestion

Date: 2026-07-09
Status: approved

## Goal

Measure how fast each Claude model (Haiku, Sonnet 5, Opus 4.8, Fable 5) burns
the rolling 5-hour usage limit, expressed in the same unit the pace system
already uses (usage% per minute), and turn that into an actionable suggestion
like `one more opus session` or `switch to fable` so the user lands at exactly
100% when the window resets.

## Hot-session suggestion (addendum, 2026-07-09)

The aggregate model suggestion says what to do in general ("switch to X");
it can't point at a specific open terminal. When pace is `ABOVE`,
`stats.session_snapshots()` scans transcript files for token activity in the
trailing 5 minutes, grouped per session (one entry per `.jsonl` file), and
`model_burn.heaviest_session()` picks the single session with the most
tokens — the one worth naming. `suggest_hot_session_action()` then prefers
`switch {project} ({session_id[:8]}) to {model}` when a lighter model would
fit the ideal rate, falling back to `kill {project} ({session_id[:8]}) -
heaviest session` when no model would help (unknown rates, or the session
is already on the lightest fit). This is a suggestion only — the dashboard
never touches processes or files belonging to another session.

Session labels use the `cwd` field each transcript line already carries,
not Claude Code's on-disk project directory name — that name encodes the
session's full absolute path with `/` replaced by `-` (e.g.
`-Users-x-Code-myrepo`), which reads as noise. `os.path.basename(cwd)` falls
back to the encoded directory name only if no line in the window carries a
`cwd`.

## What "burn rate" means

The 5h limit's `used_percentage` is model-weighted: heavier models consume the
allowance faster per token. Burn rate for a model = usage% consumed per minute
while that model is actively generating. This is measured empirically, never
hardcoded — model weights are Anthropic's internal detail and can change.

## Measurement: clean-interval attribution

New module `model_burn.py`, driven from the monitor's once-a-minute refresh
loop (no new processes; the statusline hook is untouched and stays fast).

1. Read consecutive pairs of usage samples from `history.jsonl`. Each pair is
   an interval: `(t0, t1, delta_pct)` within one 5h window.
2. Skip intervals already processed (see cursor, below), intervals that span a
   window reset (`resets_at` differs — usage% snaps back to ~0 there),
   zero-duration intervals, and intervals longer than 20 minutes:
   `history.jsonl` records change events, so a 1% tick after a long idle
   stretch spans the idle time and would dilute the measured rate.
3. For each remaining interval, scan the Claude Code transcripts under
   `~/.claude/projects` (reusing `stats.py`'s doubling tail-reader) and bucket
   token counts by `message.model` for messages timestamped inside the
   interval. Token counting matches `stats.py`: input + output +
   cache_creation, excluding cache-read.
4. If **exactly one model** produced tokens in the interval, it is a clean
   sample. Record `{model, delta_pct, duration_minutes, tokens, t0, t1}`.
   Mixed-model and zero-token intervals are discarded — attribution would be
   a guess, and guessing per-token weights is exactly what this feature is
   supposed to replace.

The user's benchmark flow (same prompt, fresh context, one model at a time,
monitor open) produces all-clean intervals by construction; no special
benchmark mode is needed. Passive day-to-day use keeps refining the numbers
whenever only one model happens to be active.

## Storage

- Clean samples append to `~/.claude/usage-monitor/model_burn.jsonl` —
  permanent, never pruned, same pattern as `window_history.jsonl`.
- Processing cursor: the max `t1` across stored samples, plus a
  `last_processed` timestamp persisted alongside (a tiny
  `model_burn_cursor.json`), so discarded (mixed/zero) intervals aren't
  rescanned forever and restarting the monitor never double-counts.
- Model names are normalized to short keys: `haiku`, `sonnet`, `opus`,
  `fable` (prefix-match on the model id, e.g. `claude-fable-5` → `fable`).
  Unrecognized model ids keep their raw id and still work.

## Averaging

Per-model average burn rate = `sum(delta_pct) / sum(duration_minutes)` over
all of that model's samples — a duration-weighted average. This is what makes
the integer-ish granularity of `used_percentage` converge: single short runs
may register only 1–2%, but the weighted average across accumulated minutes is
unbiased. A model is **eligible** for suggestions once it has ≥ 10 total clean
minutes observed.

## Estimates for unmeasured models

A model with fewer than the eligible minutes gets an **estimated** rate
instead of its noisy raw measurement: take the eligible model with the most
measured minutes as the anchor, divide its rate by its price weight, and
multiply by the target's weight. Price weights come from API pricing
(2026-07, $/MTok input — output has the identical ratio):
haiku 1 : sonnet 3 : opus 5 : fable 10. Estimates are marked `(est)` in the
panel and feed the suggestion engine like measured rates; each is replaced
by the real measurement once that model accumulates enough clean minutes.
With no eligible anchor at all, the panel still shows `collecting data` —
%/min depends on the user's plan and workload, so there is no absolute
prior to fall back to.

## Suggestion engine

Inputs, all already available in the monitor loop:

- `ideal` — ideal %/min from `pace.compute_ideal_rate` (live).
- `actual` — current %/min from `pace.compute_current_rate` (live).
- `remaining_minutes`, `used_pct` — from state.
- `current_model` — the model with the most transcript tokens in the last
  10 minutes (None if nothing generated recently).
- Per-model average rates for eligible models.

Definitions:

- `surplus_pct = (100 − used_pct) − actual × remaining_minutes` — the usage%
  that would be left unspent at reset if the current rate continues. Positive
  means under-using, negative means overshooting.
- `NOMINAL_SESSION_MINUTES = 30` — one "session" of a model costs
  `rate(model) × 30` in usage%.

Decision, in order (pace states reuse the existing badge thresholds):

1. No eligible models → `collecting data`.
2. **BELOW pace**: walk eligible models heaviest-first. If
   `surplus_pct ≥ rate(m) × NOMINAL_SESSION_MINUTES`, suggest
   `one more {m} session`. If no model's session fits but some eligible model
   other than `current_model` has `rate(m) > actual` and a rate closer to
   `ideal` than `actual` is, suggest `switch to {m}` (the closest such).
   Otherwise `stay on {current}`.
3. **ABOVE pace**: suggest `switch to {m}` where `m` is the heaviest eligible
   model with `rate(m) ≤ ideal` (phrased `stay on {m}` when that is already
   the current model). If none qualifies, `ease off - even {lightest}
   overshoots`, naming the lightest measured model.
4. **AT pace**: `stay on {current_model}` (falls back to the eligible model
   closest to ideal when current_model is unknown).

Heaviness is the measured burn rate, descending — empirical rate ordering is
what heaviness means for the limit, and it handles unknown model ids with no
special casing.

## UI

New compact panel row in `monitor.py`:

- One line per measured model: short name, avg %/min, total clean minutes
  observed (so the user can judge confidence). Models never seen don't appear.
- A highlighted suggestion line, e.g. `SUGGEST: one more opus session`,
  rendered near the existing pace badge. Shows `collecting data` dimmed until
  a model is eligible.
- No emojis anywhere, matching project style.

## Error handling

Same philosophy as the rest of the project: malformed jsonl lines skipped,
missing files mean empty data, transcript scan errors degrade to "no clean
sample this interval", and the panel degrades to `collecting data` rather than
crashing the dashboard.

## Testing

Pure-function unit tests in `tests/test_model_burn.py`, matching existing
style:

- Interval pairing from history samples (window-reset intervals skipped,
  cursor respected).
- Clean-attribution: single-model interval accepted, mixed/zero rejected.
- Duration-weighted averaging, eligibility threshold.
- Model-id normalization.
- Suggestion engine: each branch (collecting data, one-more-session,
  switch-up, switch-down, ease-off, stay), tie-breaking, unknown current
  model.

Transcript scanning reuses the already-tested tail-read machinery; the
per-model bucketing gets a test with synthetic jsonl lines.

## Known limitations

- `used_percentage` granularity (~1%) makes single short samples coarse;
  accuracy comes from accumulated minutes, not individual samples.
- Measurement only accumulates while the monitor is running (accepted
  trade-off of the monitor-loop approach).
- Burn rate depends partly on workload shape (subagent fan-out, long tool
  outputs), not just the model; the average reflects the user's real usage
  mix, which is what the suggestion should be based on anyway.
