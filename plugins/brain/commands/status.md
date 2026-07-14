---
description: What this project's brain knows, and whether its rules are earning their keep
allowed-tools: Bash
---

## Current brain

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" status 2>&1 || brain status 2>&1`

Report the above to the user as-is. Do not paraphrase the numbers.

If a rule shows 2 or more overrides, say plainly that it is one strike from retiring
itself, and ask whether they want to keep it.
