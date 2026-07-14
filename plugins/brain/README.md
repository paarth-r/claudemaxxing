# brain

Per-project memory for Claude Code, whose rules are **enforced by hooks** rather than
merely written down.

## The problem this actually solves

Agents forget project conventions. The obvious fix is to write them down, so everyone
writes an `AGENTS.md`. Then you watch an agent read it, understand it, and do the wrong
thing anyway forty tool calls later.

This project started from one repo whose `AGENTS.md` said, in plain English:

> Don't claim a fix works from logs alone. For visual/pipeline changes, view an actual
> rendered frame.

The rule was there. It was in context. Agents committed without running the pipeline
anyway, session after session, and the human re-typed the same correction every time.

**The rule was never missing. It was unenforced.** Prose in a context window is a
suggestion. A hook is not. So `brain` splits the problem in two:

- **Knowledge** — facts an agent needs to *know*. Read on demand. Costs ~200 tokens.
- **Rules** — things an agent must *do*. Enforced at the tool call. Costs **zero tokens**
  and fires every time.

A 200-line `AGENTS.md` costs thousands of tokens every session and is obeyed
inconsistently. Moving the rules into hooks is better on both axes at once.

## How enforcement works

**Receipts** make compliance verifiable instead of claimed. When a command that matters
runs, a hook records it:

```json
{"kind": "live-run", "ts": 1752537600, "cmd": "./run.sh", "exit": 0}
```

Before `git commit`, the gate asks a question it can actually answer: **is there a
passing receipt newer than the newest source edit?**

That freshness clause is the entire point. A run that predates the change you are
committing does not count. Without it the check is theatre — satisfiable by having run
the pipeline an hour ago, before the change that broke it.

If the receipt is missing or stale, the gate tries to fix it for you: it runs the rule's
remedy. If that passes, your commit goes through and you never noticed. If it fails, you
are denied — with the real error, not a nag.

## Rules

Markdown with flat frontmatter, so Obsidian renders them and a hook can execute them.
**The agent writes these. You don't.**

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
The test suite is necessary and not sufficient.
```

Nothing in the engine knows what `uv`, `pytest`, `npm`, or Python is. Every
project-specific fact — the remedy, the source glob, the receipt kind — is **data**. The
same engine expresses "rebuild `web/out` after touching `web/`", "run the sim before
pushing", or anything else, with no code change.

## Where rules come from

You never write one. Four paths, none of which need you:

| Path | When |
|---|---|
| **`brain init`** | Mines your existing `AGENTS.md` / `CLAUDE.md` / `README` for rules that can actually be checked. Day one, for free. |
| **Corrections** | You say "no, you have to live run first". That is not a task, it is a rule being restated. It gets captured. |
| **Pain** | A command failed. The resolution that finally worked is the highest-signal gotcha there is. |
| **`brain remember`** | Explicit, when you want it. |

Nothing is interpreted mid-session. A `SessionEnd` pass reads what was captured and
decides, once, what is worth writing down.

## Rules die on their own

Letting a model author enforcement is only safe if bad rules decay. They do:

- Every rule is born `severity: warn`. **The model does not get to grant itself blocking
  power** — even a rule that asks for `block` is rewritten to `warn` on the way in.
- Overridden 3 times → **archived**, with a note explaining why it died.
- A blocking rule overridden once → **demoted**.
- A `warn` rule satisfied 5 times cleanly → **promoted** to `block`. It earned it.

The thresholds are asymmetric on purpose. A wrongly-archived rule is cheap: the next
correction rewrites it. A wrongly-enforced rule is expensive: you have to fight your own
tools. So enforcement is easy to lose and slow to gain.

## Safety

This is a tool that can say no to you, so it is built so you can never get trapped.

- **It cannot deadlock.** If a rule denies a call and you retry the identical call, it is
  **allowed through** and the rule takes an override strike. A wrong rule costs you one
  turn, never a lockout.
- **It fails open.** Any crash, parse error, or timeout allows the tool call. A broken
  brain means *no brain*, never a blocked commit.
- **It never hard-blocks.** The gate denies with a reason the agent must reckon with. It
  never exits with a blocking status code.
- **Zero footprint by default.** No `.brain/` in a repo → every hook exits immediately.
  Opting one repo in cannot affect another.
- **Private by default.** `.brain/` is hidden via `.git/info/exclude`, which is
  local-only. A work repo never shows it in a diff.
- **The distiller runs with no tools and no permission bypass.** It is asked for text and
  nothing else; the plugin writes the files itself, refusing any path outside `.brain/`.

## Install

```
/plugin marketplace add paarth-r/claudemaxxing
/plugin install brain@claudemaxxing
```

Then, in a repo you want memory for:

```
brain init
```

## Config

Three layers: repo, then machine, then built-in defaults.

```yaml
# .brain/config.yml   (this repo)
paused: false
auto_remedy: true     # run the remedy automatically, or just deny with instructions
```

```yaml
# ~/.brain/config.yml   (this machine; applies to every repo)
mirror: ~/path/to/your/obsidian/vault
```

**Mirroring is off unless you configure it.** Out of the box the brain never writes a
single byte outside your repo. Set `mirror` once at the machine level and every repo
exports there automatically.

## Obsidian

Every brain is openable as an Obsidian vault — both the repo's own `.brain/` and any
mirrored copy. Wikilinks resolve, graph view works. Your vault settings are never
overwritten by an export.

A copy is used, never a symlink: iCloud mangles symlinks, and a vault symlinked into a
repo that later gets deleted leaves dead links behind.

## Commands

```
brain init        create a brain, mine rules from the repo's own docs
brain status      what it knows, and whether its rules earn their keep
brain why <id>    where a rule came from, and its track record
brain check --cmd "git commit -m x"    dry-fire the gate, no session needed
brain doctor      what is installed, what is paused, what is failing
brain pause       stop enforcing (--global for everywhere)
brain remember    write something down
brain mirror      export to the configured vault now
```

Everything works with the plugin disabled — it is plain Python over the same library the
hooks use. When the gate does something you did not expect, `brain check` reproduces the
decision with no Claude session at all.

## Kill switch

```
touch ~/.brain/DISABLED     # everything, everywhere, off
rm ~/.brain/DISABLED        # back on
```

A bare file check, on purpose: it works even if every other part of this codebase is
broken.

## Uninstall

Disable or remove the plugin. **This plugin never writes to your `settings.json`**, so
there is nothing to clean up. Your `.brain/` directories stay on disk unless you delete
them — the knowledge survives removing the tool.

## Limitations

Worth knowing before you rely on it:

- **A rule can only gate a tool call.** "Always run X before committing" is enforceable.
  "Write clean code" is not, and the distiller is told not to try.
- **Rule conflicts are not detected.** Two rules gating the same command with
  contradictory remedies will both fire. The lifecycle resolves it crudely: the wrong one
  accumulates overrides and archives itself.
- **The distiller is one model call at session end.** It can miss things, and it can
  write a rule you disagree with. That rule will decay if you keep overriding it, but it
  costs you a turn each time until it does.
- **Brains do not talk to each other.** Each repo is an island — deliberate, since it is
  what keeps a work rule out of an unrelated repo.
- **Receipts are per-session.** A live run in yesterday's session does not satisfy today's
  commit. This is intentional and occasionally annoying.

## Requirements

Python 3.9+ (whatever bare `python3` you have — macOS ships 3.9) and the `claude` CLI for
the distiller. **No third-party dependencies**, deliberately: hooks run under the system
interpreter, so assuming `pyyaml` is installed is assuming a crash on someone else's
machine.
