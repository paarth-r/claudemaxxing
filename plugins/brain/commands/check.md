---
description: Would this command be blocked? Dry-fire the gate without running anything
argument-hint: [command, e.g. git commit -m fix]
allowed-tools: Bash
---

The user wants to know whether this command would be gated: **$ARGUMENTS**

Run it through the gate without executing anything:

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" check --cmd "$ARGUMENTS" 2>&1 || brain check --cmd "$ARGUMENTS" 2>&1`

Report the decision and, if it would be denied, the rule and the remedy.
