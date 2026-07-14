# claudemaxxing

A terminal dashboard that watches Claude Code's rolling 5-hour usage limit and tells you whether you should be using Claude *more*, *less*, or you're right on pace to use your whole allowance with nothing left over. Comes with commentary from history's greatest philosophers — each now gainfully employed in tech — who have opinions about your subagent usage.

![claudemaxxing screenshot](docs/assets/screenshot.png)

<details>
<summary>What it looks like when you're burning too fast (<code>ABOVE</code> pace)</summary>

![claudemaxxing screenshot, ABOVE pace](docs/assets/screenshot-above.png)

</details>

## What it does

- Live progress bars for **usage% used** and **% of the 5-hour window elapsed**
- A real **Rate vs. Ideal** comparison: your actual recent %/min consumption rate against the ideal %/min that would land you at exactly 100% right when the window resets — recalculated live every refresh, not a static snapshot
- A **pace badge** (`ABOVE` / `AT` / `BELOW`) that tells you plainly whether to **ease off**, **use more**, or you're **right on pace** — right next to it, a live projection: `finish by 7:20pm` if your current rate would exhaust the window before it resets, or `lands at 82%` if it wouldn't
- A **"Resets in" countdown** to your next window
- A **sparkline** of your usage trend across the current window, capped to the most recent 60 samples — older points scroll off instead of wrapping the line
- Real-time **tokens/min** (from your actual Claude Code transcripts, excluding cache-read overhead so it reflects real new work) and a count of **active Claude Code sessions** running right now
- **Per-model burn rates**, shown as a table (model, rate, measured minutes): measures how fast each Claude model (Haiku, Sonnet, Opus, Fable) empirically burns the 5h limit in %/min. The table is reference data and stays visible at every pace, including `AT`. A **model suggestion** appears below it only when there's actually something to act on — `one more opus session` when you're under pace, `switch to fable`/`ease off` when you're over; at `AT` pace there's nothing to suggest, so the suggestion lines (not the table) are hidden. Models you haven't measured yet get an estimate scaled from your best-measured model by Anthropic's API price ratio (Haiku : Sonnet : Opus : Fable = 1 : 3 : 5 : 10), shown with a `~` prefix on the rate (e.g. `~1.40%/min`); ~10 minutes of single-model usage with the monitor open replaces an estimate with your real measured rate.
- A **hot-session suggestion**: whenever pace is `ABOVE`, scans your open Claude Code sessions for the one burning the most tokens/min in the last 5 minutes and names it directly — `switch claudemaxxing (2e2d1b34) to haiku` or, if no lighter model would help, `kill claudemaxxing (2e2d1b34) - heaviest session`. This is a suggestion only; the dashboard never touches your sessions.
- A **GitHub-commit-graph-style heatmap**: one cube per completed 5-hour window, shaded from grey (no usage) to green (100% peak usage), with a timeline underneath. Persists permanently across restarts so your history keeps building.
- A rotating **fake philosopher quote**, scoped to whichever pace state is active — nudges to use more when you're under, mockery of excess when you're over, wisdom about the middle way when you're right on pace. Each of the 26 philosophers has a fixed, anachronistic tech job title (Marcus Aurelius, Head of Stoic Philosophy @ McKinsey; Kafka, Founding Engineer @ Apache Kafka; Kant, Head of Multimodal Research @ Anthropic)
- Works across multiple open Claude Code sessions/terminals: they all converge on the same number instead of each showing their own stale local reading
- Clears the terminal and fills the full window height on start; refreshes once a minute

## Install

```
git clone https://github.com/paarth-r/claudemaxxing.git
cd claudemaxxing
./install.sh
```

`install.sh` installs the one Python dependency (`rich`), symlinks the `claudemaxxing` command onto your `PATH` (`~/.local/bin`), and wires a small hook into `~/.claude/settings.json` — it only adds a `statusLine` key and leaves the rest of your settings untouched.

If you've somehow managed to install and use Claude code to a point where you need this tool without using `git`, you can use GitHub's **Code → Download ZIP** button above, unzip, and run `./install.sh` from inside the folder.

Then send at least one message in any Claude Code session (so it has usage data to report), and run:

```
claudemaxxing
```

## The suite

`claudemaxxing` is also a Claude Code **plugin marketplace**. The dashboard above stays
download-and-run; the plugins install separately, and each can be paused or removed on
its own without touching anything else.

```
git clone https://github.com/paarth-r/claudemaxxing.git
cd claudemaxxing
./setup.sh
```

`setup.sh` asks which parts you want, installs them, and tells you how to undo it
(`./setup.sh --uninstall`). Or install the plugin by hand:

```
/plugin marketplace add paarth-r/claudemaxxing
/plugin install brain@claudemaxxing
```

- **[brain](plugins/brain/)** — per-project agent memory. Agents forget project
  conventions, and writing them down does not fix it: a rule in a markdown file is a
  suggestion, and at tool-call 40 the agent commits anyway. `brain` moves rules out of
  prose and into hooks, where a `git commit` that skipped the required run is actually
  stopped rather than merely tut-tutted at. It proves compliance with **receipts** — a
  run only counts if it happened *after* the code it is meant to validate. Rules cost
  zero context tokens, cannot deadlock you, and fail open.

## How it works

Anthropic doesn't expose a public "check my usage" API. Claude Code itself computes your 5-hour usage percentage internally and only surfaces it through its **statusLine** feature — a small script you register in `settings.json` that Claude Code invokes on every render with the current rate-limit data on stdin.

This project's statusline hook (`usage_statusline.py`) captures that data into a shared local file every time any Claude Code session renders, instead of making any direct calls to Anthropic's API. A separate long-running TUI (`monitor.py`) polls that file once a minute and draws the dashboard.

Four things worth knowing:
- If a session's own last-known reading lags behind another session's, the hook always reconciles toward the more advanced (higher, or newer-window) value, so every open session's statusline — and the dashboard — shows the same number. A lagging session reporting an *older* window is rejected outright, so it can't regress the shared state backward.
- Pace is a rate comparison, not a snapshot: it looks at your usage% change over the last ~15 minutes to get a real %/min rate, compares it against `(100% − used%) / minutes remaining`, and both sides shift continuously as you use Claude and time passes.
- Per-model burn attribution is conservative: a usage% delta only becomes a measurement when exactly one model was generating tokens during that interval (checked against your local transcripts). Mixed-model intervals and long idle gaps are discarded rather than guessed at. Samples persist forever in `~/.claude/usage-monitor/model_burn.jsonl`, so the averages keep sharpening across restarts.
- The hot-session suggestion identifies sessions by scanning transcript files, using the `cwd` each session recorded rather than Claude Code's on-disk directory naming (which encodes the full path with `/` → `-` and isn't readable). It picks the single project + session id with the highest token/min in the trailing 5 minutes — not a list, since only the worst offender is actionable.
- If no Claude Code session is open at all, the dashboard shows a dimmed `STALE` badge rather than pretending the data is current.

## Requirements

- Python 3
- [Claude Code](https://claude.ai/code)
- `rich` (installed automatically by `install.sh`)

121 tests covering the pace math, multi-session merge logic, per-model burn attribution, hot-session detection, and file I/O — `pytest` (dev only, not needed to run the tool).

## License

MIT
