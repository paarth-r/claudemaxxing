---
description: Is the brain actually working? Shows what is installed, paused, or failing
allowed-tools: Bash
---

## Diagnostics

!`python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" doctor 2>&1 || brain doctor 2>&1`

Report this to the user.

If "brain here" says none, this repo has no brain and every hook is a no-op here —
tell them to run `/brain:init` to opt this repo in.

If there are recent hook errors, surface them; they are the reason something is not
working.
