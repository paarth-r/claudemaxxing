---
description: Give this repo a brain, mining rules from the docs it already has
allowed-tools: Bash
---

Opt this repo into per-project memory.

```
python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" init
```

This reads the repo's own `AGENTS.md`, `CLAUDE.md`, and `README` and turns the
enforceable statements in them into rules a hook can actually check. It hides
`.brain/` from git via `.git/info/exclude`, which is local-only — nothing appears in
the repo's diff.

It calls a model once, so it takes a few seconds. Report exactly what it wrote.

Tell the user the rules start on probation (`warn`) and earn the right to block by
being right repeatedly.
