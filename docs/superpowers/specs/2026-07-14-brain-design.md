# brain — per-project agent memory with enforceable rules

Design spec. 2026-07-14.

## Problem

Agents forget project conventions across sessions, and re-teaching them costs the
user real time on every new session.

The naive diagnosis is "the docs are missing." That is wrong, and the evidence is
storePose. Its `AGENTS.md` is 200 lines, genuinely good, and already contains the
rule the user keeps having to repeat:

> After any change, run `uv run pytest` from the repo root and report the real
> result. Don't claim a fix works from logs/CSVs alone — for visual/pipeline
> changes, view an actual rendered frame.

The rule is written down. It is loaded into context. It is still ignored. So there
are two distinct failures here, and they need two different mechanisms:

1. **Knowledge failure** — the agent does not *know* a fact about the repo (that
   `calib/` is busy-ness calibration and not camera geometry; that a stale
   `web/out` silently degrades to a legacy UI). Documentation fixes this.
   `AGENTS.md` is already good at it.
2. **Compliance failure** — the agent *knows* the rule, the rule is in its context
   window, and at tool-call 40 it commits anyway. **Documentation cannot fix
   this.** Prose in a context window is a suggestion. The only thing that reliably
   stops an agent at the moment of action is a hook.

Writing a prettier, more linked, Obsidian-native copy of `AGENTS.md` would address
(1), which is not broken, and do nothing for (2), which is.

A third constraint sits on top: whatever we build must not bloat the context
window, and must not require the user to maintain it.

## Goals

- Rules that are **enforced**, not merely documented.
- Knowledge that **accumulates without user intervention**.
- **Near-zero context cost** at rest.
- Native **Obsidian** browsing and graphing, integrated with the existing vault.
- **Installable, pausable, and removable** without endangering the user's setup.

## Non-goals

- Replacing `AGENTS.md` / `CLAUDE.md`. The brain complements them.
- Sharing the brain with teammates by default. (storePose is a Mashgin repo with
  an IP-assignment clause; FRC 254 is a shared team repo. Default is private.)
- A retrieval/embedding system. A thin index plus on-demand reads is sufficient at
  this scale and has no moving parts.

## Generality

storePose is the **proving ground, not the target**. The system must work unchanged
on Hyperform, AOS, the campus game, and repos that do not exist yet. Nothing in
`hookkit` may know what `uv`, `pytest`, or Python is.

The design generalizes because every project-specific thing is **data in a rule file**,
never code:

| Project-specific thing | Where it lives | Generic mechanism |
|---|---|---|
| "live run before commit" | a rule's `trigger` + `satisfied_by` | match a tool call; look for a receipt |
| `./run.sh --source videos/test.mp4` | a rule's `remedy.command` | run an arbitrary shell command |
| `src/**` | a rule's `fresher_than` glob | compare mtimes against a glob |
| `live-run` | a rule's `receipt` kind | receipt kinds are arbitrary strings |

So the same engine expresses "run the C++ sim before pushing to AOS", "rebuild
`web/out` after touching `web/`", "never commit raw footage", or "run the stereo rig
calibration check before changing camera code" — with no change to the code, only new
rule files the agent writes.

### Bootstrap: no repo starts empty

`/brain init` seeds a repo by **ingesting what it already has**: `AGENTS.md`,
`CLAUDE.md`, `README`, `CONTRIBUTING`, and CI config. A one-shot Sonnet pass turns
imperative statements already written down ("always run X", "never use Y", "rebuild Z
after touching W") into rules and gotchas.

This is high-leverage precisely because those documents are where good rules go to be
ignored. storePose's `AGENTS.md` alone yields the live-run rule, the `avc1`-not-`mp4v`
rule, the stale-`web/out` rule, and the no-raw-footage privacy rule — all of which are
already written, and none of which are currently enforced. Bootstrapping converts
existing dead prose into live enforcement on day one, in any repo.

Bootstrapped rules are born `severity: warn` like any other, so a bad read of a README
decays on its own rather than wedging a new project.

## Core mechanism: receipts

Compliance fails today because it is **unverifiable**. The agent can claim it live-ran.
It can believe it live-ran. Nothing checks.

A **receipt** is an append-only record that something actually happened, written by
a `PostToolUse` hook when the agent runs a command that matters:

```jsonl
{"kind":"live-run","ts":1752537600,"cmd":"./run.sh --source videos/test.mp4","exit":0}
```

The `PreToolUse` gate on `git commit` then asks a question it can actually answer:
**is there a `live-run` receipt newer than the newest edit under `src/`?**

That freshness clause is load-bearing. A live run that predates the last source
edit does not satisfy the rule. Without it, the check is theater — satisfiable by
having run the pipeline an hour ago, before the change that broke it.

Receipts are per-session, stored at `.brain/_receipts/<session_id>.jsonl`, and are
always gitignored (they contain command lines).

## Gate behavior

Per the user's decision: **soft block with attempted auto-execute to correct.**

```
git commit
  -> no rule matches                    -> allow (silent)
  -> rule matches, receipt fresh        -> allow (silent)
  -> rule matches, receipt stale/absent
       -> auto_remedy enabled?
            no  -> DENY with the command in the reason; agent runs it, retries
            yes -> execute remedy (bounded by timeout)
                     exit 0        -> write receipt -> ALLOW. user never notices.
                     non-zero      -> DENY, handing the agent the real stderr
                     timeout/error -> ALLOW + additionalContext warning (fail open)
```

When the code is fine this is invisible: the hook runs the smoke test and passes
the commit through. It only speaks up when something is genuinely broken, and what
it says is a real failure, not a nag.

`auto_remedy` is a per-repo config flag, default `true`. Setting it `false` gives
deny-only behavior with no background execution.

Mechanically, per the Claude Code hook protocol:
- **Deny with a reason the agent reads**: exit 0, stdout
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}`
- **Allow with an injected warning**: same shape, `permissionDecision: "allow"` plus
  `additionalContext`.
- Exit 2 is never used. It blocks with less control, and we never want a hard block.

## Rule format

Obsidian-native markdown, so rules render and graph in the vault. YAML frontmatter,
so a hook can execute them. **The agent authors these. The user never hand-writes one.**

```markdown
---
id: live-run-before-commit
type: rule
severity: warn                  # warn | block  (self-promoting, see below)
trigger:
  tool: Bash
  pattern: '^git (commit|push)'
satisfied_by:
  receipt: live-run
  fresher_than: 'src/**'        # receipt must postdate newest matching source edit
remedy:
  command: './run.sh --source videos/test.mp4'
  timeout: 300
provenance:
  source: correction            # correction | distillation | pain | explicit
  session: 4c8f2a1b
  date: 2026-07-14
  quote: "no, you have to live run before you push"
stats:
  fired: 3
  satisfied: 2
  overridden: 0
---

# Live run before commit

Tests pass on code paths that render as green static in the actual video.
`uv run pytest` is necessary and not sufficient.

Related: [[gotchas/mp4v-green-static]] [[utils/smoke-run]]
```

### Overrides, and why the gate can never deadlock

A rule that is simply wrong must not be able to deny the same commit forever. So the
gate is **self-releasing**:

- First denial of a given tool call: deny, with the remedy in the reason.
- **The identical tool call, denied again by the same rule → ALLOW**, with a warning
  in `additionalContext`, and record an **override** in the rule's `stats`.

This guarantees no deadlock is possible: the worst a bad rule can cost is one wasted
agent turn. It also means the demotion signal is generated automatically — a rule
that keeps getting overridden is, by construction, a rule that keeps being wrong, and
it archives itself. The user can also force one explicitly with `/brain override <id>`.

`severity: warn` and `severity: block` differ only in the reason text and how many
overrides they tolerate before demoting (`warn`: 1, `block`: 3). Neither can hard-fail
a session.

### Self-tuning (the safety valve for agent-authored rules)

Letting the model write its own enforcement is only safe if bad rules die on their
own. They do:

- A new rule is born `severity: warn`.
- Fires repeatedly without being overridden → **auto-promotes to `block`.**
- Overridden repeatedly (threshold: 3) → **auto-demotes to `warn`, then archives**
  to `.brain/_archive/` with a note explaining why it died.

Rules reflecting real constraints harden. Rules the agent hallucinated decay and
fall out. The user never has to file a bug against their own memory system. The
`stats` block is the evidence trail; `brain why <rule>` prints it.

## Capture: how the brain learns

All four paths write. None require the user to do anything.

| Path | Trigger | What it captures |
|---|---|---|
| **Correction** | `UserPromptSubmit` flags correction-shaped prompts ("no, you have to...", "never...", "always...") | Queues the prompt. The distiller turns it into a **rule**. This is the direct fix for the storePose complaint. |
| **Pain** | `PostToolUseFailure`, plus repeated failures of the same command | The wall the agent hit and the resolution that finally worked, with its cost in tool calls. Highest-signal gotchas. |
| **Distillation** | `SessionEnd` | A headless Sonnet pass over the transcript writes what it learned about the repo: structure, gotchas, commands. Broad coverage of knowledge never explicitly stated. |
| **Explicit** | `/brain remember <thing>` | Escape hatch. Direct write. |

Correction and pain **queue** during the session (cheap, no LLM call). Only
`SessionEnd` invokes a model, reusing the `synthesize-session.py` pattern already
in the user's setup: find the transcript, invoke a headless `claude -p` on Sonnet,
write files. It runs only on substantial sessions (>= 3 user turns).

## Retrieval: why this does not bloat context

Two halves, and neither is expensive:

- **Rules cost zero context tokens.** They live in hooks. A rule fires 100% of the
  time and occupies nothing in the agent's window. Compare with today: 200 lines of
  `AGENTS.md` prose costs thousands of tokens and is obeyed inconsistently. Moving
  rules from prose into hooks is strictly better on *both* axes at once.
- **Knowledge is a thin index plus on-demand reads.** A `SessionStart` hook injects
  only `.brain/index.md` as `additionalContext` — note titles and one-line hooks,
  ~200 tokens. The agent reads a full note only when it is about to touch that area.
  A 3,000-token brain costs ~200 tokens at rest.

```
## storePose brain
Read a note before touching its area.

gotchas/calib-is-not-camera-calib  - calib/ is busy-ness, not geometry
gotchas/web-out-silent-fallback    - stale web/out = silent legacy UI
gotchas/mp4v-green-static          - codec must be avc1
map/data-flow                      - per-frame pipeline
utils/smoke-run                    - canonical run command

12 rules ACTIVE (enforced by hook, not loaded)
```

The index is regenerated by the distiller. It is never hand-maintained.

Note: the index is injected by a hook, **not** by an `@import` in `CLAUDE.md`. This
keeps the repo byte-for-byte clean, works whether or not `.brain/` is committed, and
disappears automatically when the plugin is disabled.

## Storage and the vault

`.brain/` is **canonical in the repo** and **gitignored by default**:

```
~/Code/storePose/.brain/
  index.md                      # thin index (generated)
  config.yml                    # paused, auto_remedy, mirror
  rules/*.md
  gotchas/*.md
  map/*.md
  utils/*.md
  _archive/                     # rules that decayed and died
  _receipts/<session>.jsonl     # always gitignored
```

Repo-canonical means hooks need **zero mapping layer**: the hook runs with `cwd`
inside the repo, walks up to find `.brain/`, done. No registry keyed on git remote
to drift out of sync.

Gitignored-by-default means nothing leaks into Mashgin's repo or FRC's team repo.
`brain init --shared` opts a repo in to committing its brain.

**Vault mirroring is a one-way file copy, not a symlink.** On `SessionEnd`, `.brain/`
(minus `_receipts/`) is copied to
`secondbrain/projects/<repo>/`. Symlinks were rejected: iCloud Drive mangles them
(dehydrating them into broken aliases), and an Obsidian vault symlinked into a repo
that later gets `rm -rf`'d leaves a vault full of dead links. A copy gives Obsidian
graphing *and* survives repo deletion. The mirror is derived and read-only; nothing
ever syncs back.

Mirrored notes use vault frontmatter conventions (`type`, `domain`, `updated`) and
wikilink out to the existing knowledgebase — `[[project_storepose]]`,
`[[storepose-backlog]]` — so the project brain joins the existing graph rather than
sitting beside it.

## Blast radius

The user's explicit constraint: this must not endanger their setup, or anyone else's.
Four independent layers, each sufficient alone.

1. **Fail open, always.** Every hook is wrapped so any unhandled exception, parse
   error, or timeout exits 0 and allows the action. A memory system must never be
   able to stop the user from committing code. The failure mode of a broken brain is
   "no brain," never "cannot work." This aligns with the platform default: only exit
   2 blocks; every other error is non-blocking.
2. **Opt-in per repo; default footprint is zero.** Every hook's first action is to
   look for `.brain/` walking up from `cwd`. Absent → exit immediately. Repos without
   `brain init` are untouched. A bad rule in storePose cannot affect Hyperform.
3. **Kill switch at two scopes.** `brain pause` (this repo, via `config.yml`) and
   `brain pause --global` (touches `~/.brain/DISABLED`). Checked before any other
   work, so the panic button is a single `touch` and works even if the Python is
   broken.
4. **Install/uninstall never touches `settings.json`.** Shipping as a Claude Code
   plugin makes lifecycle native: install via marketplace, pause by flipping
   `enabledPlugins`, uninstall by disabling. The user's `statusLine` (which points
   at `claudemaxxing`), their two existing `SessionEnd` hooks, and their four enabled
   plugins are never rewritten, because we never write to that file at all.
   `brain uninstall` leaves `.brain/` directories on disk; `--purge` removes them.

## Repo organization

`claudemaxxing` is the **suite** (and eventually a control panel). The usage
dashboard keeps the name `claudemaxxing`. `brain` is a sibling tool within the
suite, not part of the dashboard.

The change to the existing repo is **purely additive**:

```
claudemaxxing/                      <- the suite (existing repo)
  monitor.py, pace.py, install.sh   <- UNTOUCHED. still git clone && ./install.sh
  .claude-plugin/marketplace.json   <- NEW: makes the repo a marketplace
  packages/hookkit/                 <- NEW: shared core, reused by every plugin
  plugins/brain/
    .claude-plugin/plugin.json
    hooks/hooks.json
    skills/brain/SKILL.md           <- /brain init, remember, status, why, pause
    scripts/                        <- 5 thin hook entrypoints over hookkit
  tests/
```

The dashboard's files are deliberately **not** relocated: the user's live
`settings.json` `statusLine` points at an absolute path into this repo, so moving
`usage_statusline.py` would silently break their statusline on the next pull.

A marketplace may list plugins hosted in other repos, so the suite can grow to
include external tools without absorbing them.

### Components

| Component | Responsibility |
|---|---|
| `packages/hookkit/` | Fail-open wrapper, kill-switch check, `.brain/` discovery, receipt read/write, rule parsing and matching, the PreToolUse JSON protocol. Pure library, no I/O with Claude. |
| `plugins/brain/scripts/guard.py` | `PreToolUse`. Match rule → check receipt freshness → auto-remedy → allow/deny. |
| `plugins/brain/scripts/receipt.py` | `PostToolUse` / `PostToolUseFailure`. Emit receipts; record pain events. |
| `plugins/brain/scripts/capture.py` | `UserPromptSubmit`. Flag and queue correction-shaped prompts. |
| `plugins/brain/scripts/distill.py` | `SessionEnd`. Headless Sonnet pass → write notes/rules → regenerate index → mirror to vault. |
| `plugins/brain/scripts/context.py` | `SessionStart`. Inject `index.md` as `additionalContext`. |
| `plugins/brain/skills/brain/` | The `/brain` skill: `init`, `remember`, `status`, `why`, `pause`, `doctor`. |

Every hook script is a thin entrypoint; the logic lives in `hookkit` where it is
unit-testable without a running Claude session.

## Error handling

- Any hook exception → log to `.brain/_log/hook-errors.log`, exit 0. Never surfaced
  to the user mid-task.
- Remedy timeout → allow with an `additionalContext` warning. Never leaves the user
  hanging on a commit.
- Malformed rule file → skip that rule, log, continue with the others. One bad rule
  cannot disable the gate.
- Distiller failure → session ends normally. The brain simply does not learn from
  that session. Queued corrections persist for the next distillation.
- Vault unavailable (iCloud not materialized) → skip the mirror, log. Never blocks.

## Testing

pytest, matching `claudemaxxing`'s existing convention. The tests that carry weight:

- **Hook contract**: recorded stdin JSON → assert exact stdout JSON and exit code,
  for allow / deny / warn / fail-open paths.
- **Receipt freshness**: a receipt predating the newest `src/` edit must NOT satisfy
  the rule. This is the test that keeps the mechanism honest.
- **Promote/demote state machine**: an overridden rule must actually demote and
  archive; an unchallenged rule must promote.
- **Fail-open**: inject exceptions at every hook entrypoint; assert exit 0 and that
  the tool call proceeds.
- **Zero-footprint**: in a repo with no `.brain/`, assert every hook is a no-op.
- **Mirror**: idempotent, one-way, excludes `_receipts/`.

Debuggability, since the user asked for it explicitly:
- `brain check --tool Bash --cmd "git commit"` — dry-fire the gate with no session.
- `brain doctor` — print what is registered, what fired, what is paused, recent errors.
- `brain why <rule-id>` — provenance and stats: where this rule came from, the quote
  that produced it, how often it fired, whether it is earning its keep.

## Milestones

Each milestone is independently useful and independently verifiable. The system is
not worth anything until M2 proves the core claim, so M2 is the real bar.

- **M1 — Skeleton.** `hookkit` + marketplace + plugin manifest + a no-op hook that
  proves the plugin loads, fires, and is a strict no-op in repos without `.brain/`.
  Verifiable: install it, see it do nothing, disable it, see it gone.
- **M2 — The gate (the whole point).** Receipts, rule parsing, `PreToolUse`
  auto-remedy, self-releasing override. Hand-write one rule file and prove that
  `git commit` without a fresh live run is actually stopped, and that a commit *with*
  one sails through untouched. storePose is the proving ground because its failure is
  already documented and reproducible. **If this milestone does not visibly change
  agent behavior there, the design is wrong and the rest should not be built.**
  Generality is proved in the same milestone by expressing a second, structurally
  different rule from another repo (e.g. rebuild `web/out` after touching `web/`) with
  no code change — only a new rule file.
- **M3 — Capture.** `/brain init` bootstrap from existing docs, `UserPromptSubmit`
  correction queue, pain events, `SessionEnd` distiller. Verifiable two ways: run
  `init` on a repo and see rules mined out of its existing `AGENTS.md`; and correct
  the agent once, end the session, see a rule file the agent wrote appear, then watch
  it fire in the next session.
- **M4 — Retrieval.** Index generation + `SessionStart` injection. Verifiable: index
  is under ~250 tokens and the agent reads a note only when it needs one.
- **M5 — Vault.** One-way mirror into `secondbrain/projects/`, wikilinked into the
  existing graph. Verifiable: open Obsidian, see the project brain in graph view.
- **M6 — Ergonomics.** `brain doctor`, `check`, `why`, `pause`, `uninstall`. README.

## Open questions

None. All design decisions are settled:
enforcement (soft block + auto-remedy, config-toggleable), storage (repo-canonical,
gitignored, vault-mirrored by copy), capture (all four paths), retrieval (thin index
+ on-demand), packaging (plugin in the claudemaxxing suite marketplace).
