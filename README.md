# claudemaxxing

A terminal dashboard that watches Claude Code's rolling 5-hour usage limit and tells you whether you're on pace to hit 100% before it resets. Comes with commentary from history's greatest philosophers, who have opinions about your subagent usage.

![claudemaxxing screenshot](docs/assets/screenshot.png)

## What it does

- Live progress bars for **usage% used** and **% of the 5-hour window elapsed**
- A **pace badge** (`ABOVE` / `AT` / `BELOW`) telling you whether you're burning faster or slower than time is passing
- A **sparkline** of your usage trend across the current window
- A rotating **fake philosopher quote** — wisdom about restraint when you're pacing fine, mockery of excess when you're not
- Works across multiple open Claude Code sessions/terminals: they all converge on the same number instead of each showing their own stale local reading
- Refreshes once a minute

## Install

```
git clone https://github.com/paarth-r/claudemaxxing.git
cd claudemaxxing
./install.sh
```

`install.sh` installs the one Python dependency (`rich`), symlinks the `claudemaxxing` command onto your `PATH` (`~/.local/bin`), and wires a small hook into `~/.claude/settings.json` — it only adds a `statusLine` key and leaves the rest of your settings untouched.

No `git` handy? Use GitHub's **Code → Download ZIP** button above, unzip, and run `./install.sh` from inside the folder.

Then send at least one message in any Claude Code session (so it has usage data to report), and run:

```
claudemaxxing
```

## How it works

Anthropic doesn't expose a public "check my usage" API. Claude Code itself computes your 5-hour usage percentage internally and only surfaces it through its **statusLine** feature — a small script you register in `settings.json` that Claude Code invokes on every render with the current rate-limit data on stdin.

This project's statusline hook (`usage_statusline.py`) captures that data into a shared local file every time any Claude Code session renders, instead of making any direct calls to Anthropic's API. A separate long-running TUI (`monitor.py`) polls that file once a minute and draws the dashboard.

Two things worth knowing:
- If a session's own last-known reading lags behind another session's, the hook always reconciles toward the more advanced (higher, or newer-window) value, so every open session's statusline — and the dashboard — shows the same number.
- If no Claude Code session is open at all, the dashboard shows a dimmed `STALE` badge rather than pretending the data is current.

## Requirements

- Python 3
- [Claude Code](https://claude.ai/code)
- `rich` (installed automatically by `install.sh`)

## License

MIT
