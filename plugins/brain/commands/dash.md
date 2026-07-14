---
description: Open a graph view of this project's brain — which rules are working, which are dying
allowed-tools: Bash
---

Serve the brain graph for this repo.

This is a long-running server, so run it in the BACKGROUND (do not block on it):

```
python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" dash
```

Then tell the user the localhost URL it printed, and that Ctrl-C stops it.

The graph shows what Obsidian's cannot: each rule's track record. A rule that keeps
being overridden is drawn dying and drifts to the edge of the graph; one that earned
the right to block sits solid at the centre. Rules are listed by who is in trouble.

If this repo has no brain, say so and offer `/brain:init` instead of starting a server.
