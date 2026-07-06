# Claude Code Usage Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone terminal tool (`claude-usage`) that shows live progress toward Claude Code's rolling 5-hour usage limit, fed by a Claude Code statusLine hook, with rotating fake-philosopher commentary.

**Architecture:** A statusLine script (`usage_statusline.py`) that Claude Code invokes on every render writes `state.json` + appends `history.jsonl` under `~/.claude/usage-monitor/`. A separate long-running TUI (`monitor.py`, `rich`-based) polls those files every 60s and renders progress bars, a pace badge, a sparkline, and a quote. Pure calculation logic (elapsed%, pace, staleness) lives in its own module so it's unit-testable without a terminal. A thin shell wrapper installed as `claude-usage` on PATH launches the TUI.

**Tech Stack:** Python 3, `rich` (pip), `pytest` (dev/test only)

## Global Constraints

- Data source is exclusively the statusLine JSON payload — no direct Anthropic API calls, no reading OAuth credentials. (Design spec: "Why this data source")
- Pace deadband is exactly 3 percentage points: `ABOVE` if `used% - elapsed% > 3`, `BELOW` if `< -3`, else `AT`.
- Stale threshold is exactly 600 seconds (10 minutes) since `state.json`'s mtime.
- `history.jsonl` only ever contains samples whose `resets_at` is still in the future — pruned on every statusline write.
- Quotes: two pools (`FRUGAL_QUOTES`, `EXCESS_QUOTES`), 30-50 entries each, each a `(quote_text, philosopher)` tuple, all Claude-Code-flavored humor attributed to real philosophers.
- A new quote is drawn only when pace status transitions (not every poll).
- All file paths under `~/.claude/usage-monitor/`: `state.json`, `history.jsonl`. Repo lives at `~/Code/usage-monitor/`.

---

### Task 1: Quotes module

**Files:**
- Create: `~/Code/usage-monitor/quotes.py`
- Test: `~/Code/usage-monitor/tests/test_quotes.py`

**Interfaces:**
- Produces: `FRUGAL_QUOTES: list[tuple[str, str]]`, `EXCESS_QUOTES: list[tuple[str, str]]`, `pick_quote(pool: list[tuple[str,str]]) -> tuple[str,str]`

- [ ] **Step 1: Write the failing tests**

```python
# ~/Code/usage-monitor/tests/test_quotes.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quotes import FRUGAL_QUOTES, EXCESS_QUOTES, pick_quote

def test_pools_have_enough_quotes():
    assert 30 <= len(FRUGAL_QUOTES) <= 50
    assert 30 <= len(EXCESS_QUOTES) <= 50

def test_pools_have_no_duplicates():
    assert len(set(FRUGAL_QUOTES)) == len(FRUGAL_QUOTES)
    assert len(set(EXCESS_QUOTES)) == len(EXCESS_QUOTES)

def test_quotes_are_text_philosopher_pairs():
    for quote, philosopher in FRUGAL_QUOTES + EXCESS_QUOTES:
        assert isinstance(quote, str) and len(quote) > 0
        assert isinstance(philosopher, str) and len(philosopher) > 0

def test_pick_quote_returns_from_pool():
    for _ in range(20):
        result = pick_quote(FRUGAL_QUOTES)
        assert result in FRUGAL_QUOTES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_quotes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quotes'`

- [ ] **Step 3: Write the quotes module**

```python
# ~/Code/usage-monitor/quotes.py
import random

FRUGAL_QUOTES = [
    ("A wise man drives subagents; a fool develops inline.", "Plato"),
    ("He who compacts his context before it compacts him needs no reset.", "Sun Tzu"),
    ("The unexamined token is not worth spending.", "Socrates"),
    ("Patience is bitter, but its fruit is a fresh five-hour window.", "Aristotle"),
    ("He who forks wisely need never force-push in anger.", "Confucius"),
    ("The master delegates to the subagent and claims the credit; this too is virtue.", "Lao Tzu"),
    ("Know thyself, and thy context window.", "Socrates"),
    ("A single well-placed hook is worth a thousand manual checks.", "Marcus Aurelius"),
    ("The frugal engineer writes one commit for one thought.", "Seneca"),
    ("To cache is human; to recompute, folly.", "Epictetus"),
    ("He who reads the plan before acting wastes no tokens undoing.", "Confucius"),
    ("Small tasks, done in order, outlast grand designs abandoned at forty percent context.", "Marcus Aurelius"),
    ("The barrel that is never overfilled never spills.", "Diogenes"),
    ("I think, therefore I do not need three parallel agents to think for me.", "Descartes"),
    ("He who waits for the plan mode gate builds on rock, not sand.", "Aristotle"),
    ("The river that flows steadily reaches the sea; the one that floods reaches only ruin.", "Heraclitus"),
    ("Moderation in all things, even in the summoning of Opus.", "Aristotle"),
    ("A man who tests before he ships needs no apology after.", "Seneca"),
    ("The wise haiku model does more with less; be like the haiku model.", "Lao Tzu"),
    ("He who reads the diff before committing sees his own folly first.", "Socrates"),
    ("Virtue lies in the middle path between no agents and twenty agents.", "Aristotle"),
    ("The still mind writes the shorter prompt.", "Zhuangzi"),
    ("He who prunes his history file keeps his garden and his graph.", "Voltaire"),
    ("Better one skill invoked well than ten tools invoked poorly.", "Confucius"),
    ("The five-hour window is long to him who does not squander it before lunch.", "Seneca"),
    ("To automate wisely is to labor once and rest four times.", "Epictetus"),
    ("He who reads the error message first debugs twice as fast.", "Marcus Aurelius"),
    ("The disciplined mind schedules its wakeups; the anxious mind polls forever.", "Epictetus"),
    ("A tool used once and put away outlives a tool left running unwatched.", "Diogenes"),
    ("The wise do not mistake motion for progress, nor tokens for thought.", "Lao Tzu"),
    ("He who commits often fears no rebase.", "Sun Tzu"),
    ("Restraint today buys context tomorrow.", "Marcus Aurelius"),
]

EXCESS_QUOTES = [
    ("He who forks ten agents to write one commit message has not saved time, only borrowed shame from the future.", "Nietzsche"),
    ("Man's greatest hubris is not fire, but setting reasoning effort to max for a spelling fix.", "Nietzsche"),
    ("He who summons Opus to summarize a haiku has lost the plot entirely.", "Kafka"),
    ("The abyss stares back, mostly to ask why you opened forty parallel tabs.", "Nietzsche"),
    ("There is no context window deep enough for a man who refuses to compact.", "Kafka"),
    ("He who spawns a subagent to spawn a subagent has built not a tool, but a bureaucracy.", "Kafka"),
    ("God is dead, and so is your five-hour window, by eleven in the morning.", "Nietzsche"),
    ("The absurd man reads no docs and re-derives the wheel, hourly.", "Camus"),
    ("One does not simply request medium effort when max is available; this is the tragedy of man.", "Sophocles"),
    ("The overconfident engineer forks first and reads the diff never.", "Machiavelli"),
    ("To rate-limit a man is to reveal what he truly worshipped: his own throughput.", "Nietzsche"),
    ("There is no sin greater than re-reading a file you just wrote, out of anxiety.", "Kafka"),
    ("He who requests the highest reasoning effort for hello world insults both the machine and himself.", "Diogenes"),
    ("The trial has no end, and neither does your context, for you never once compacted it.", "Kafka"),
    ("Ambition is calling twelve tools when one grep would have sufficed.", "Machiavelli"),
    ("He who polls every second has mistaken anxiety for diligence.", "Epicurus"),
    ("He who builds twelve microservices for a to-do list has confused architecture with anxiety.", "Machiavelli"),
    ("The will to power is, in the end, just wanting Opus for everything.", "Nietzsche"),
    ("He who never lets his agent rest burns twice as bright and finishes the window by noon.", "Heraclitus"),
    ("Absurdity is asking why the rate limit exists while triggering it for the fifth time this hour.", "Camus"),
    ("He who mistakes verbosity for thoroughness will exhaust the well before noon.", "Schopenhauer"),
    ("Hell is other agents' context, all crammed into yours.", "Sartre"),
    ("Whereof one cannot summarize, thereof one must keep prompting anyway.", "Wittgenstein"),
    ("The state of nature is nasty, brutish, and short, much like your remaining five-hour budget.", "Hobbes"),
    ("Man is born free, and everywhere he is in rate-limit chains of his own making.", "Rousseau"),
    ("The owl of Minerva spreads its wings only at dusk, long after you should have stopped forking agents.", "Hegel"),
    ("He who cannot explain his own workflow to himself has automated only his confusion.", "Wittgenstein"),
    ("Give a man a hammer and every problem becomes a twenty-agent orchestration.", "Nietzsche"),
    ("The examined life includes examining why you have six background tasks running at once.", "Socrates"),
    ("He who greedily hoards tokens for later finds later never comes, only the reset.", "Diogenes"),
    ("Pride goeth before a five-hour lockout.", "Sophocles"),
    ("The unexamined subagent spawns unexamined subagents, world without end.", "Kafka"),
]

def pick_quote(pool):
    return random.choice(pool)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_quotes.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/Code/usage-monitor && git add quotes.py tests/test_quotes.py && git commit -m "Add philosopher quote pools"
```

---

### Task 2: Pace calculation module

**Files:**
- Create: `~/Code/usage-monitor/pace.py`
- Test: `~/Code/usage-monitor/tests/test_pace.py`

**Interfaces:**
- Produces: `compute_elapsed_percentage(resets_at: float, now: float, window_seconds: float = 18000) -> float`, `compute_pace(used_pct: float, elapsed_pct: float, deadband: float = 3.0) -> str` (returns `"ABOVE"`, `"AT"`, or `"BELOW"`), `is_stale(mtime: float, now: float, threshold_seconds: float = 600) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# ~/Code/usage-monitor/tests/test_pace.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pace import compute_elapsed_percentage, compute_pace, is_stale

def test_elapsed_percentage_at_window_start():
    now = 1000
    resets_at = now + 18000
    assert compute_elapsed_percentage(resets_at, now) == 0.0

def test_elapsed_percentage_halfway():
    now = 1000
    resets_at = now + 9000
    assert compute_elapsed_percentage(resets_at, now) == 50.0

def test_elapsed_percentage_past_reset_clamps_to_100():
    now = 1000
    resets_at = now - 5
    assert compute_elapsed_percentage(resets_at, now) == 100.0

def test_pace_above():
    assert compute_pace(used_pct=60, elapsed_pct=50) == "ABOVE"

def test_pace_below():
    assert compute_pace(used_pct=40, elapsed_pct=50) == "BELOW"

def test_pace_at_within_deadband():
    assert compute_pace(used_pct=51, elapsed_pct=50) == "AT"
    assert compute_pace(used_pct=48, elapsed_pct=50) == "AT"

def test_is_stale():
    now = 10000
    assert is_stale(mtime=now - 601, now=now) is True
    assert is_stale(mtime=now - 599, now=now) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_pace.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pace'`

- [ ] **Step 3: Write the pace module**

```python
# ~/Code/usage-monitor/pace.py

def compute_elapsed_percentage(resets_at, now, window_seconds=18000):
    remaining = resets_at - now
    if remaining <= 0:
        return 100.0
    if remaining >= window_seconds:
        return 0.0
    return (1 - remaining / window_seconds) * 100

def compute_pace(used_pct, elapsed_pct, deadband=3.0):
    diff = used_pct - elapsed_pct
    if diff > deadband:
        return "ABOVE"
    if diff < -deadband:
        return "BELOW"
    return "AT"

def is_stale(mtime, now, threshold_seconds=600):
    return (now - mtime) > threshold_seconds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_pace.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/Code/usage-monitor && git add pace.py tests/test_pace.py && git commit -m "Add pace/elapsed/staleness calculation module"
```

---

### Task 3: State I/O module

**Files:**
- Create: `~/Code/usage-monitor/state_io.py`
- Test: `~/Code/usage-monitor/tests/test_state_io.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `STATE_PATH: str`, `HISTORY_PATH: str`, `read_state(path=STATE_PATH) -> dict | None`, `read_history(path=HISTORY_PATH) -> list[dict]`, `write_state(snapshot: dict, path=STATE_PATH) -> None`, `append_history(sample: dict, path=HISTORY_PATH) -> None`, `prune_history(now: float, path=HISTORY_PATH) -> None` (drops lines whose `resets_at` <= now)

- [ ] **Step 1: Write the failing tests**

```python
# ~/Code/usage-monitor/tests/test_state_io.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state_io import read_state, read_history, write_state, append_history, prune_history

def test_read_state_missing_file_returns_none(tmp_path):
    assert read_state(str(tmp_path / "missing.json")) is None

def test_write_then_read_state_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    write_state({"used_percentage": 42, "resets_at": 123}, path)
    assert read_state(path) == {"used_percentage": 42, "resets_at": 123}

def test_read_history_missing_file_returns_empty_list(tmp_path):
    assert read_history(str(tmp_path / "missing.jsonl")) == []

def test_append_and_read_history(tmp_path):
    path = str(tmp_path / "history.jsonl")
    append_history({"timestamp": 1, "used_percentage": 10, "resets_at": 100}, path)
    append_history({"timestamp": 2, "used_percentage": 20, "resets_at": 100}, path)
    samples = read_history(path)
    assert len(samples) == 2
    assert samples[0]["used_percentage"] == 10
    assert samples[1]["used_percentage"] == 20

def test_read_history_skips_corrupt_lines(tmp_path):
    path = str(tmp_path / "history.jsonl")
    with open(path, "w") as f:
        f.write('{"timestamp": 1, "used_percentage": 10, "resets_at": 100}\n')
        f.write("not json\n")
        f.write('{"timestamp": 2, "used_percentage": 20, "resets_at": 100}\n')
    samples = read_history(path)
    assert len(samples) == 2

def test_prune_history_drops_expired_windows(tmp_path):
    path = str(tmp_path / "history.jsonl")
    append_history({"timestamp": 1, "used_percentage": 10, "resets_at": 50}, path)
    append_history({"timestamp": 2, "used_percentage": 20, "resets_at": 200}, path)
    prune_history(now=100, path=path)
    samples = read_history(path)
    assert len(samples) == 1
    assert samples[0]["resets_at"] == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_state_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'state_io'`

- [ ] **Step 3: Write the state_io module**

```python
# ~/Code/usage-monitor/state_io.py
import json
import os

STATE_PATH = os.path.expanduser("~/.claude/usage-monitor/state.json")
HISTORY_PATH = os.path.expanduser("~/.claude/usage-monitor/history.jsonl")


def _ensure_parent_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def read_state(path=STATE_PATH):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def write_state(snapshot, path=STATE_PATH):
    _ensure_parent_dir(path)
    with open(path, "w") as f:
        json.dump(snapshot, f)


def read_history(path=HISTORY_PATH):
    samples = []
    if not os.path.exists(path):
        return samples
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return samples


def append_history(sample, path=HISTORY_PATH):
    _ensure_parent_dir(path)
    with open(path, "a") as f:
        f.write(json.dumps(sample) + "\n")


def prune_history(now, path=HISTORY_PATH):
    samples = [s for s in read_history(path) if s.get("resets_at", 0) > now]
    _ensure_parent_dir(path)
    with open(path, "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_state_io.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/Code/usage-monitor && git add state_io.py tests/test_state_io.py && git commit -m "Add state/history file I/O module"
```

---

### Task 4: StatusLine hook script + wire into Claude Code

**Files:**
- Create: `~/Code/usage-monitor/usage_statusline.py`
- Test: `~/Code/usage-monitor/tests/test_usage_statusline.py`
- Modify: `~/.claude/settings.json` (add `statusLine` key)

**Interfaces:**
- Consumes: `state_io.write_state`, `state_io.append_history`, `state_io.prune_history` (Task 3)
- Produces: a script runnable as `python3 usage_statusline.py` reading a JSON payload on stdin and printing a status string on stdout

- [ ] **Step 1: Write the failing test**

```python
# ~/Code/usage-monitor/tests/test_usage_statusline.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_statusline import build_snapshot, format_statusline

def test_build_snapshot_extracts_five_hour_fields():
    payload = {"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": 999}}}
    snapshot = build_snapshot(payload, now=100)
    assert snapshot == {"timestamp": 100, "used_percentage": 42, "resets_at": 999}

def test_build_snapshot_returns_none_when_five_hour_absent():
    assert build_snapshot({"rate_limits": {}}, now=100) is None
    assert build_snapshot({}, now=100) is None

def test_format_statusline():
    assert format_statusline(42) == "5h: 42% used"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_usage_statusline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'usage_statusline'`

- [ ] **Step 3: Write the statusline script**

```python
# ~/Code/usage-monitor/usage_statusline.py
import json
import sys
import time

from state_io import write_state, append_history, prune_history


def build_snapshot(payload, now):
    five_hour = payload.get("rate_limits", {}).get("five_hour")
    if not five_hour:
        return None
    return {
        "timestamp": now,
        "used_percentage": five_hour["used_percentage"],
        "resets_at": five_hour["resets_at"],
    }


def format_statusline(used_percentage):
    return f"5h: {used_percentage}% used"


def main():
    try:
        payload = json.load(sys.stdin)
        now = time.time()
        snapshot = build_snapshot(payload, now)
        if snapshot is None:
            return
        write_state(snapshot)
        append_history(snapshot)
        prune_history(now=now)
        print(format_statusline(snapshot["used_percentage"]))
    except Exception:
        # Never let a statusline error break the user's Claude Code session.
        return


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Code/usage-monitor && python3 -m pytest tests/test_usage_statusline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Manual smoke test with fake stdin**

Run: `echo '{"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":9999999999}}}' | python3 ~/Code/usage-monitor/usage_statusline.py`
Expected output: `5h: 42% used`
Then verify: `cat ~/.claude/usage-monitor/state.json` shows `{"timestamp": ..., "used_percentage": 42, "resets_at": 9999999999}`

- [ ] **Step 6: Wire into Claude Code settings**

Read `~/.claude/settings.json`, add (merging with any existing keys — do not overwrite unrelated settings):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /Users/paarth-r/Code/usage-monitor/usage_statusline.py"
  }
}
```

- [ ] **Step 7: Commit**

```bash
cd ~/Code/usage-monitor && git add usage_statusline.py tests/test_usage_statusline.py && git commit -m "Add statusLine hook script that captures rate-limit snapshots"
```

---

### Task 5: Monitor TUI

**Files:**
- Create: `~/Code/usage-monitor/monitor.py`
- Create: `~/Code/usage-monitor/requirements.txt`

**Interfaces:**
- Consumes: `state_io.read_state`, `state_io.read_history`, `state_io.STATE_PATH` (Task 3); `pace.compute_elapsed_percentage`, `pace.compute_pace`, `pace.is_stale` (Task 2); `quotes.FRUGAL_QUOTES`, `quotes.EXCESS_QUOTES`, `quotes.pick_quote` (Task 1)
- Produces: a runnable `python3 monitor.py` that renders a live-updating terminal display, polling every 60 seconds

This task has no automated test (terminal rendering isn't practically unit-testable) — verification is a manual run.

- [ ] **Step 1: Write requirements.txt**

```
rich>=13.0.0
```

- [ ] **Step 2: Install rich**

Run: `cd ~/Code/usage-monitor && pip3 install -r requirements.txt`
Expected: successful install (or "already satisfied")

- [ ] **Step 3: Write monitor.py**

```python
# ~/Code/usage-monitor/monitor.py
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.text import Text

from state_io import read_state, read_history, STATE_PATH
from pace import compute_elapsed_percentage, compute_pace, is_stale
from quotes import FRUGAL_QUOTES, EXCESS_QUOTES, pick_quote

import os

POLL_SECONDS = 60
SPARK_CHARS = "▁▂▃▄▅▆▇█"

console = Console()


def sparkline(values):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    return "".join(
        SPARK_CHARS[min(int((v - lo) / span * (len(SPARK_CHARS) - 1)), len(SPARK_CHARS) - 1)]
        for v in values
    )


def pace_color(pace):
    return {"ABOVE": "red", "AT": "yellow", "BELOW": "green"}[pace]


def render(state, history, last_quote):
    if state is None:
        return Panel(Text("Waiting for first Claude Code render...", style="dim"),
                      title="Claude Usage Monitor")

    used_pct = state["used_percentage"]
    resets_at = state["resets_at"]
    now = time.time()
    elapsed_pct = compute_elapsed_percentage(resets_at, now)
    pace = compute_pace(used_pct, elapsed_pct)

    body = []

    used_bar = ProgressBar(total=100, completed=used_pct, width=40)
    body.append(Text(f"Usage:   {used_pct:5.1f}% ", style="bold"))
    body.append(used_bar)

    elapsed_bar = ProgressBar(total=100, completed=elapsed_pct, width=40)
    body.append(Text(f"Elapsed: {elapsed_pct:5.1f}% ", style="bold"))
    body.append(elapsed_bar)

    body.append(Text(f"\nPace: {pace}", style=f"bold {pace_color(pace)}"))

    try:
        mtime = os.path.getmtime(STATE_PATH)
        if is_stale(mtime, now):
            body.append(Text("  [STALE]", style="dim"))
    except FileNotFoundError:
        pass

    values = [s["used_percentage"] for s in history]
    if values:
        body.append(Text(f"\n\n{sparkline(values)}", style="cyan"))

    if last_quote:
        quote_text, philosopher = last_quote
        body.append(Text(f"\n\n· \"{quote_text}\" —{philosopher} ·", style="dim italic"))

    return Panel(Group(*body), title="Claude Usage Monitor (5h window)")


def main():
    last_pace = None
    last_quote = None

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            state = read_state()
            history = read_history()

            if state is not None:
                now = time.time()
                elapsed_pct = compute_elapsed_percentage(state["resets_at"], now)
                pace = compute_pace(state["used_percentage"], elapsed_pct)
                if pace != last_pace:
                    pool = EXCESS_QUOTES if pace == "ABOVE" else FRUGAL_QUOTES
                    last_quote = pick_quote(pool)
                    last_pace = pace

            live.update(render(state, history, last_quote))
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Manual smoke test**

Run: `echo '{"rate_limits":{"five_hour":{"used_percentage":15,"resets_at":'$(($(date +%s)+16000))'}}}' | python3 ~/Code/usage-monitor/usage_statusline.py`

Then run: `cd ~/Code/usage-monitor && timeout 5 python3 monitor.py || true`
Expected: a panel renders showing Usage ~15%, an Elapsed bar, a pace badge, and a quote line — no crash/traceback.

- [ ] **Step 5: Commit**

```bash
cd ~/Code/usage-monitor && git add monitor.py requirements.txt && git commit -m "Add live TUI monitor with progress bars, sparkline, and pace-based quotes"
```

---

### Task 6: `claude-usage` command

**Files:**
- Create: `~/Code/usage-monitor/bin/claude-usage`
- Modify: installs a copy/symlink at `~/.local/bin/claude-usage` (already on `PATH` — confirmed via `which claude` resolving to `~/.local/bin/claude`)

**Interfaces:**
- Consumes: `monitor.py` (Task 5)
- Produces: a `claude-usage` command runnable from any directory

- [ ] **Step 1: Write the wrapper script**

```bash
#!/usr/bin/env bash
exec python3 "$HOME/Code/usage-monitor/monitor.py" "$@"
```

Save to `~/Code/usage-monitor/bin/claude-usage`.

- [ ] **Step 2: Make it executable and symlink onto PATH**

Run: `chmod +x ~/Code/usage-monitor/bin/claude-usage && ln -sf ~/Code/usage-monitor/bin/claude-usage ~/.local/bin/claude-usage`

- [ ] **Step 3: Verify it resolves and runs**

Run: `which claude-usage`
Expected: `/Users/paarth-r/.local/bin/claude-usage`

Run: `timeout 5 claude-usage || true`
Expected: same panel render as Task 5's smoke test, no crash.

- [ ] **Step 4: Commit**

```bash
cd ~/Code/usage-monitor && git add bin/claude-usage && git commit -m "Add claude-usage CLI entry point"
```

---

## Final End-to-End Verification

- [ ] Confirm `~/.claude/settings.json` has the `statusLine` command wired (Task 4, Step 6).
- [ ] Start a fresh Claude Code session anywhere and send one message, so Claude Code renders its statusline at least once.
- [ ] Confirm `~/.claude/usage-monitor/state.json` now reflects real (non-fake) usage data.
- [ ] Run `claude-usage` in a separate terminal and confirm it shows real usage%, a plausible elapsed%, and a pace badge that matches (usage% vs elapsed%).
- [ ] Leave it running past a 60s boundary and confirm elapsed% ticks upward on its own.
