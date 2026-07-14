# brain

Per-project agent memory for Claude Code. Rules the agent writes, and hooks
actually enforce.

Agents forget project conventions. The usual answer is to write them down — but a
rule in a markdown file is a suggestion, and at tool-call 40 the agent commits
anyway. This project exists because of a specific, repeated failure: a repo whose
`AGENTS.md` says, in plain English, "run the pipeline against real footage before
you claim this works" — and agents that read it, understood it, and committed
anyway, session after session.

The rule was never missing. It was unenforced. `brain` moves rules out of prose and
into hooks, where a `git commit` that skipped the live run is actually stopped
rather than merely tut-tutted at.

## How it works

**Receipts** make compliance verifiable. When the agent runs a command that matters,
a `PostToolUse` hook records that it actually happened, and whether it passed:

```
{"kind": "live-run", "ts": 1752537600, "cmd": "./run.sh", "exit": 0}
```

A `PreToolUse` hook on `git commit` then asks a question it can actually answer:
**is there a passing receipt newer than the newest source edit?** That freshness
clause is the whole point. A live run that predates the change you are committing
does not count — without it, the check would be theatre, satisfiable by having run
the pipeline an hour ago, before the change that broke it.

If the receipt is missing or stale, the gate tries to fix it for you: it runs the
rule's remedy command. If that passes, your commit goes through and you never
noticed. If it fails, you get denied — with the real error, not a nag.

## Rules

Rules are markdown with flat frontmatter, so Obsidian renders them and a hook can
execute them. The agent writes these; you do not.

```markdown
---
id: live-run-before-commit
severity: warn
trigger.tool: Bash
trigger.pattern: ^git (commit|push)
satisfied_by.receipt: live-run
satisfied_by.fresher_than: src/**
remedy.command: ./run.sh --source videos/test.mp4
remedy.timeout: 300
emits.pattern: ^(\./run\.sh|uv run python main\.py)
stats.fired: 3
stats.satisfied: 2
stats.overridden: 0
---

# Live run before commit

Tests pass on code paths that render as green static in the actual video.
`uv run pytest` is necessary and not sufficient.
```

Nothing in the engine knows what `uv`, `pytest`, or Python is. Every
project-specific fact — the remedy, the source glob, the receipt kind — is data in
the rule file. The same engine expresses "rebuild `web/out` after touching `web/`",
"run the sim before pushing", or anything else, with no code change.

## Safety

This is a tool that can say no to you, so it is built to be impossible to get
trapped by.

- **It cannot deadlock.** If a rule denies a call and you retry the identical call,
  it is **allowed through** and the rule takes an override strike. A wrong rule costs
  you one turn, never a lockout.
- **It fails open.** Any crash, parse error, or timeout allows the tool call. A
  broken brain means no brain, never a blocked commit. Errors are logged, not thrown
  in your face.
- **It never hard-blocks.** The gate denies with a reason the agent must reckon with.
  It never exits with a blocking status code.
- **Zero footprint by default.** No `.brain/` in a repo, no effect at all — every hook
  exits immediately. Opting one repo in cannot affect another.
- **Private by default.** `.brain/` is gitignored unless you explicitly share it.

## Install

```
/plugin marketplace add paarth-r/claudemaxxing
/plugin install brain@claudemaxxing
```

Then, in any repo you want a brain for, create `.brain/rules/` and drop a rule in.

## Pause

```
touch ~/.brain/DISABLED     # everything, everywhere, off
rm ~/.brain/DISABLED        # back on
```

Per-repo, set `paused: true` in `.brain/config.yml`. The global switch is a bare file
check on purpose: it works even if every other part of this codebase is broken.

## Uninstall

Disable or remove the plugin. **This plugin never writes to your `settings.json`**, so
there is nothing to clean up. Your `.brain/` directories stay on disk unless you delete
them — your accumulated knowledge survives removing the tool.

## Requirements

Python 3.9+ (whatever bare `python3` you have — macOS ships 3.9). No third-party
dependencies, deliberately: hooks run under the system interpreter, so assuming
`pyyaml` is present is assuming a crash on someone else's machine.
