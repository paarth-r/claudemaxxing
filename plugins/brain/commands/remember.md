---
description: Write a project convention down so it stops needing to be repeated
argument-hint: [the rule, e.g. always live-run before committing]
allowed-tools: Bash
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" remember "$ARGUMENTS" 2>&1 || brain remember "$ARGUMENTS" 2>&1`

Confirm to the user that this is now queued, and that it becomes an enforced rule at
the end of this session — so they should not have to say it again.
