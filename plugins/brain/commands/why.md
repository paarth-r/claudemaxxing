---
description: Where a rule came from, and whether it has earned its keep
argument-hint: [rule-id]
allowed-tools: Bash
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" why "$ARGUMENTS" 2>&1 || brain why "$ARGUMENTS" 2>&1`

Show the user the rule and its track record.

If they do not know the rule id, run `/brain:status` first to list them.
