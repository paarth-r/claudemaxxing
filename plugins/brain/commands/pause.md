---
description: Stop enforcing rules — this repo, or everywhere
argument-hint: [--global for everywhere]
allowed-tools: Bash
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" pause $ARGUMENTS 2>&1 || brain pause $ARGUMENTS 2>&1`

Confirm what is now paused.

Remind them that `/brain:resume` turns it back on, and that the hooks are already
silent — nothing needs restarting.
