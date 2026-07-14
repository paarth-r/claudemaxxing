# Heatmap: Fit Cube Count to Terminal Width

2026-07-14

## Problem

`render_heatmap` calls `build_cube_row(..., max_cubes=20)` via the function's
hardcoded default. 20 cubes at `CUBE_WIDTH=4` + `GAP_WIDTH=1` renders at
`20*4 + 19*1 = 99` characters — wider than an 80-column terminal, and static
regardless of how wide the terminal actually is. The heatmap should show as
much backlog as fits the current terminal width, always anchored so today
(the in-progress window) stays the rightmost cube, same as today.

## Change

New pure function in `heatmap.py`:

```python
def cubes_that_fit(available_width, cube_width=CUBE_WIDTH, gap_width=GAP_WIDTH):
    """How many cubes (with gaps between them) fit in available_width,
    minimum 1 - the in-progress window's cube must always show even on a
    pathologically narrow terminal."""
    return max(1, (available_width + gap_width) // (cube_width + gap_width))
```

Derivation: N cubes with N-1 gaps between them occupy
`N*cube_width + (N-1)*gap_width` characters. Solving for the largest N that
fits `available_width`: `N <= (available_width + gap_width) / (cube_width + gap_width)`.

`monitor.py`'s `render_heatmap` computes `available_width` from
`console.width` minus 4 (2 chars for the Panel's left+right border, 2 for
its default `padding=(0, 1)` left+right padding — the actual overhead the
Panel imposes today) and passes the result as `max_cubes` to
`build_cube_row`, replacing the implicit default of 20:

```python
available_width = console.width - 4
cubes = build_cube_row(window_history, current_peak_pct, current_window_end,
                        now, max_cubes=cubes_that_fit(available_width))
```

`console.width` is queried fresh every call (same as `console.height` is
already used for the Panel's `height=` today), so the cube count adapts
automatically on terminal resize — no caching, no resize event handling
needed.

## Non-goals

- No change to `build_cube_row`'s signature or its right-anchoring logic
  (`entries[-max_cubes:]`) — it already accepts `max_cubes` as a parameter;
  only the caller's value changes.
- No change to cube color, gap width, or the "X ago ... now" timeline label
  row — `total_width` in `render_heatmap` is already derived from the actual
  cube count, so it adapts for free once that count changes.
- No explicit terminal-resize event handling — polling `console.width` once
  per render (same cadence as everything else in the dashboard) is
  sufficient.

## Testing

`tests/test_heatmap.py`: `cubes_that_fit` — a typical width (e.g. 76 chars,
matching an 80-col terminal minus the 4-char overhead, should yield 15),
an exact-fit boundary, and a very narrow width that floors to 1.

`tests/test_monitor.py`: a test that renders with a `Console` fixed at a
specific width (not the real terminal, to avoid flakiness) and asserts the
rendered cube line's length changes between a narrow and a wide console
width — confirming the wiring, not just the pure function in isolation.

## Docs

No README change needed — the heatmap bullet already describes the
behavior ("one cube per completed 5-hour window... with a timeline
underneath") without committing to a specific cube count, so nothing there
becomes inaccurate.
