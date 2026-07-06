# Claude Code Usage Monitor — Design

## Purpose

A small standalone terminal tool that watches Claude Code's rolling 5-hour
usage limit and shows, at a glance, whether usage is on pace to hit 100%
before the window resets. Polls once a minute. Bonus: rotating fake
philosopher quotes commenting on your pace.

## Why this data source

Anthropic does not expose a public "check my usage" API. Claude Code itself
computes `rate_limits.five_hour.{used_percentage,resets_at}` internally and
only surfaces it through the **statusLine** feature — a JSON payload fed to
a user-configured script on stdin, refreshed while a Claude Code session is
active and rendering. There is no way to fetch this independently of an
active session without reverse-engineering internal rate-limit headers,
which was explicitly ruled out in favor of the documented, stable mechanism.

**Consequence:** the monitor's data is only as fresh as the last time a
Claude Code session rendered its statusline. If no session is open, the
display shows a STALE badge rather than fabricating freshness.

## Components

### 1. StatusLine hook script
`~/.claude/scripts/usage-statusline.py`

Configured as `statusLine` in `~/.claude/settings.json`. Claude Code invokes
it on every render with JSON on stdin. Responsibilities:

- Parse `rate_limits.five_hour.used_percentage` and `.resets_at` from stdin.
- Append `{timestamp, used_percentage, resets_at}` to
  `~/.claude/usage-monitor/history.jsonl`.
- Prune any lines whose `resets_at` is in the past (keeps the file scoped to
  the current 5h window only).
- Overwrite `~/.claude/usage-monitor/state.json` with the latest snapshot.
- Print `5h: {used_percentage}% used` to stdout (this becomes the visible
  Claude Code statusline text — currently nothing is shown there today).

If `rate_limits.five_hour` is absent from stdin (e.g., before the first API
response of a session), the script leaves existing state alone and prints
nothing.

### 2. Standalone TUI
`~/Code/usage-monitor/monitor.py` (Python 3 + `rich`)

Run manually in its own terminal (`python3 monitor.py`). Every 60 seconds:

- Read `~/.claude/usage-monitor/state.json` and `history.jsonl`.
- Compute:
  - **usage%** — `state.used_percentage`
  - **elapsed%** — `100 - (seconds_until(resets_at) / (5*3600) * 100)`,
    clamped to [0, 100]
  - **pace** — `ABOVE` if `usage% - elapsed% > 3`, `BELOW` if
    `elapsed% - usage% > 3`, else `AT` (3-point deadband to avoid flicker)
- Render:
  - Progress bar: usage% used
  - Progress bar: elapsed% of window
  - Pace badge: ABOVE (red) / AT (yellow) / BELOW (green)
  - Sparkline/line graph of usage% samples from `history.jsonl` across the
    current window
  - STALE badge (dimmed) if `state.json`'s mtime is more than 10 minutes old
  - Footer quote line (see below)
- Recompute elapsed% and pace every tick even if `state.json` hasn't
  changed — wall-clock time moves regardless of statusline refresh cadence.

On first run, if `state.json` doesn't exist yet, show "waiting for first
Claude Code render" instead of erroring.

### 3. Philosopher quotes

Two curated pools of Claude-Code-flavored one-liners, each in the voice of
the user's example (`"A wise man drives subagents; a fool develops inline."
—Plato`), attributed to real philosophers:

- **Frugal pool** (30-50 quotes) — shown when pace is `AT` or `BELOW`.
  Wisdom about restraint, patience, efficient tool use.
- **Excess pool** (30-50 quotes) — shown when pace is `ABOVE`. Mockery of
  burning through limits, greed, wastefulness.

Stored as two Python lists in `quotes.py`. A quote is drawn at random from
the matching pool **only on a pace-status transition**
(BELOW→AT, AT→ABOVE, ABOVE→AT, etc.) — not every 60s tick — so it reads as
commentary rather than noise. The chosen quote persists in the footer until
the next transition.

Visual treatment mirrors Claude Code's own rotating status captions
(the "Cogitating…" style spinner text): small, dim/italic, single line, no
border or box. Example: `· "A wise man drives subagents; a fool develops
inline." —Plato ·`

## Data flow

```
Claude Code renders statusline
  → usage-statusline.py parses stdin, writes state.json + appends history.jsonl
  → monitor.py polls state.json/history.jsonl every 60s
  → recomputes elapsed%/pace live regardless of poll finding new data
  → on pace transition, draws new quote from matching pool
  → renders bars + graph + badges + quote
```

## Error handling

- Missing `state.json` on first run → friendly waiting message, no crash.
- Stale state (>10 min old) → dimmed STALE badge, numbers still shown as
  last-known.
- `history.jsonl` corrupt line → skip that line, don't crash the graph.
- statusLine script errors → fail silently (print nothing), never break the
  user's actual Claude Code session.

## Out of scope

- Tracking the `seven_day` limit (available in the same payload, but not
  requested — left for a future iteration if wanted).
- Making direct Anthropic API calls or touching OAuth credentials.
- Persisting history across multiple 5h windows (only the current window is
  graphed).
