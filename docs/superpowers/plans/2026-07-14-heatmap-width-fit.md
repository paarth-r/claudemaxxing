# Heatmap Width-Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the commit-graph-style heatmap show as many cubes as fit the actual terminal width (always right-anchored to today) instead of a hardcoded cap of 20.

**Architecture:** One new pure function in `heatmap.py` (`cubes_that_fit`) computes the cube count from an available-width number. `monitor.py`'s `render_heatmap` gains an optional `console_width` parameter — defaulting to the module-level `console.width` (queried fresh every call, same as `console.height` already is) — and uses it to compute `max_cubes` instead of relying on `build_cube_row`'s hardcoded default of 20.

**Tech Stack:** Python 3, `rich` (Console/Text), `pytest`.

## Global Constraints

- No change to `build_cube_row`'s signature or its right-anchoring logic (`entries[-max_cubes:]`) — only the value the caller passes for `max_cubes` changes.
- No change to cube color, gap width, or the "X ago ... now" timeline label row.
- No explicit terminal-resize event handling — polling width once per render is sufficient (matches the existing `console.height` pattern already used for the Panel).

---

### Task 1: `cubes_that_fit` in `heatmap.py`

**Files:**
- Modify: `heatmap.py` (append function at end of file)
- Test: `tests/test_heatmap.py` (append tests at end of file)

**Interfaces:**
- Produces: `cubes_that_fit(available_width, cube_width=CUBE_WIDTH, gap_width=GAP_WIDTH) -> int` — the largest cube count (minimum 1) whose total rendered width (`N*cube_width + (N-1)*gap_width`) fits within `available_width`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_heatmap.py`:

```python
from heatmap import cubes_that_fit

def test_cubes_that_fit_typical_width():
    # 76 chars (an 80-col terminal minus 4 chars of Panel border+padding)
    # -> (76+1)//5 = 15 cubes
    assert cubes_that_fit(76) == 15

def test_cubes_that_fit_exact_boundary():
    # 10 cubes at CUBE_WIDTH=4, GAP_WIDTH=1 occupy exactly 10*4 + 9*1 = 49
    assert cubes_that_fit(49) == 10
    # one char narrower no longer fits a 10th cube
    assert cubes_that_fit(48) == 9

def test_cubes_that_fit_floors_to_one_on_narrow_width():
    assert cubes_that_fit(0) == 1
    assert cubes_that_fit(-10) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_heatmap.py -v -k cubes_that_fit`
Expected: FAIL with `ImportError: cannot import name 'cubes_that_fit'`.

- [ ] **Step 3: Implement `cubes_that_fit`**

Append to `heatmap.py`:

```python
def cubes_that_fit(available_width, cube_width=CUBE_WIDTH, gap_width=GAP_WIDTH):
    """How many cubes (with gaps between them) fit in available_width,
    minimum 1 - the in-progress window's cube must always show even on a
    pathologically narrow terminal."""
    return max(1, (available_width + gap_width) // (cube_width + gap_width))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_heatmap.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Commit**

```bash
git add heatmap.py tests/test_heatmap.py
git commit -m "feat: add cubes_that_fit for width-aware heatmap sizing"
```

---

### Task 2: Wire `cubes_that_fit` into `monitor.py`'s `render_heatmap`

**Files:**
- Modify: `monitor.py:20` (import), `monitor.py:74-75` (`render_heatmap` signature and `build_cube_row` call)
- Test: `tests/test_monitor.py` (append tests at end of file)

**Interfaces:**
- Consumes: `cubes_that_fit(available_width)` from Task 1.
- Produces: `render_heatmap(window_history, current_peak_pct, current_window_end, now, console_width=None)` — when `console_width` is omitted, falls back to the module-level `console.width`. Callers that already call `render_heatmap(window_history, used_pct, resets_at, now)` (i.e. the one call site inside `render()`) are unaffected since the new parameter is optional.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_monitor.py`:

```python
from monitor import render_heatmap

def _cube_row_pixel_width(cube_line):
    return len(cube_line.plain)

def test_render_heatmap_uses_more_cubes_on_a_wider_console():
    now = 100000
    window_history = [{"resets_at": now - i * 18000, "peak_usage_percentage": 50} for i in range(1, 30)]
    narrow_cube_line, _ = render_heatmap(window_history, 10, now + 18000, now, console_width=30)
    wide_cube_line, _ = render_heatmap(window_history, 10, now + 18000, now, console_width=200)
    assert _cube_row_pixel_width(wide_cube_line) > _cube_row_pixel_width(narrow_cube_line)

def test_render_heatmap_defaults_to_module_console_width():
    # No console_width passed -> falls back to the module-level console.width
    # rather than raising or silently doing nothing.
    now = 100000
    result = render_heatmap([], 10, now + 18000, now)
    assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_monitor.py -v -k render_heatmap`
Expected: FAIL — `render_heatmap()` currently takes no `console_width` keyword argument (`TypeError: render_heatmap() got an unexpected keyword argument 'console_width'`).

- [ ] **Step 3: Add the `console_width` parameter and wire it through**

In `monitor.py`, update the import from `heatmap` (currently):

```python
from heatmap import build_cube_row, color_for_pct, format_time_ago, CUBE_WIDTH, GAP_WIDTH
```

to:

```python
from heatmap import build_cube_row, cubes_that_fit, color_for_pct, format_time_ago, CUBE_WIDTH, GAP_WIDTH
```

Then replace `render_heatmap`'s signature and its `build_cube_row` call (currently):

```python
def render_heatmap(window_history, current_peak_pct, current_window_end, now):
    cubes = build_cube_row(window_history, current_peak_pct, current_window_end, now)
```

with:

```python
def render_heatmap(window_history, current_peak_pct, current_window_end, now, console_width=None):
    if console_width is None:
        console_width = console.width
    available_width = console_width - 4  # 2 chars Panel border + 2 chars default padding
    cubes = build_cube_row(window_history, current_peak_pct, current_window_end, now,
                           max_cubes=cubes_that_fit(available_width))
```

(The rest of `render_heatmap` — building `cube_line`, `total_width`, and `timeline` — stays exactly as-is; it already derives everything from `len(cubes)`, so it adapts automatically.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_monitor.py -v`
Expected: PASS (all tests in the file, old and new).

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: PASS, all tests across `tests/` — no regressions from the `render_heatmap` signature change (its one call site inside `render()` doesn't pass `console_width`, so it keeps using the module-level `console.width` by default).

- [ ] **Step 6: Manually verify the rendered output**

Run: `python3 -c "
import time
from monitor import render
now = time.time()
state = {'used_percentage': 40, 'resets_at': now + 3000}
history = [{'timestamp': now - 600, 'used_percentage': 35, 'resets_at': now + 3000}]
window_history = [{'resets_at': now - i * 18000, 'peak_usage_percentage': 30 + i} for i in range(1, 30)]
from rich.console import Console
Console().print(render(state, history, None, None, window_history, None, None))
"`

Expected: a panel whose heatmap row shows as many cubes as fit the terminal you're running this in (not capped at 20), with the timeline label (`X ago ... now`) still aligned under the cube row and nothing wrapping or overflowing the panel border.

- [ ] **Step 7: Commit**

```bash
git add monitor.py tests/test_monitor.py
git commit -m "feat: size the heatmap to the actual terminal width"
```
