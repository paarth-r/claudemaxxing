---
name: brain
description: Manage this project's brain - the rules and knowledge that persist across sessions. Use when the user says /brain, asks to remember a project convention, asks why a commit was blocked, wants to see or pause the project's rules, or wants to set up memory for a repo. Also use when the user is correcting a repeated mistake and it should be written down permanently rather than said again.
---

# brain

Per-project memory whose rules are enforced by hooks rather than merely written down.

Run the CLI with `python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" <command>` from inside the
repo. Report what it prints; do not paraphrase a blocked-commit reason away.

## Commands

| The user says | Run |
|---|---|
| "set up a brain here", "remember things about this repo" | `init` |
| "what does the brain know?", "what rules are active?" | `status` |
| "why was that blocked?", "where did that rule come from?" | `why <rule-id>` |
| "would this be blocked?" | `check --cmd "git commit -m x"` |
| "is the brain working?", something seems broken | `doctor` |
| "stop enforcing", "turn it off" | `pause` (add `--global` for everywhere) |
| "turn it back on" | `resume` |
| "remember that <X>" | `remember "<X>"` |
| "sync it to my vault" | `mirror` |

## init

`init` mines the repo's own `AGENTS.md`, `CLAUDE.md`, and `README` for rules that can
actually be checked, and writes them into `.brain/rules/`. This is high-leverage
precisely because those files are where good rules go to be ignored.

It hides `.brain/` from git via `.git/info/exclude`, which is local-only. A work repo
never shows the brain in its diff.

## When the user corrects you

If the user is telling you something they have clearly told you before - a convention,
a prohibition, a step you keep skipping - that is a rule, not a task. It is already
being captured automatically, but you can make it explicit:

    python3 "${CLAUDE_PLUGIN_ROOT}/cli.py" remember "always live-run before committing"

Then say you have written it down so it stops needing to be said.

## When a commit is blocked

The gate denied a tool call because a rule was not satisfied. Do not fight it and do
not immediately retry to force the override through. Read the reason:

- If it names a remedy command, **run the remedy**, then retry.
- If the remedy ran and failed, **the code is broken**. Fix it.
- If the rule genuinely does not apply, retrying the identical command releases it, and
  the rule takes an override strike. Three strikes and it archives itself. Tell the
  user you are doing this and why.

## Rules are never hand-written

Rules start as `severity: warn` and earn the right to `block` by being right
repeatedly. Do not edit `severity:` by hand, and do not write rule files directly
unless the user explicitly asks. Let corrections and the session-end distiller create
them.
