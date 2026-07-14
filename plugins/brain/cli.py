#!/usr/bin/env python3
"""brain: the command line.

Everything here works with the plugin disabled - it is plain Python over the same
library the hooks use. That matters for debugging: when the gate does something you
did not expect, you can reproduce it without a Claude session.

    brain init          create a brain here, and mine rules out of the repo's own docs
    brain status        what this brain knows, and whether its rules earn their keep
    brain why <id>      where a rule came from, and its track record
    brain check         dry-fire the gate against a command, with no session
    brain doctor        what is installed, what is paused, what has been failing
    brain pause         stop enforcing (--global for everywhere)
    brain resume
    brain remember      write something down for the next distillation
    brain mirror        export to the configured vault now
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hookkit import distiller, index, mirror, queue, receipts, vault  # noqa: E402
from hookkit.config import get  # noqa: E402
from hookkit.discovery import find_brain, repo_root  # noqa: E402
from hookkit.gate import decide  # noqa: E402
from hookkit.killswitch import is_disabled  # noqa: E402
from hookkit.rules import load_rules  # noqa: E402

BOOTSTRAP_SOURCES = ("AGENTS.md", "CLAUDE.md", "README.md", "CONTRIBUTING.md")


def _brain_or_die(quiet=False):
    brain = find_brain(Path.cwd())
    if brain is None:
        if not quiet:
            print("No brain here. Run `brain init` to create one.")
        sys.exit(1)
    return brain


def _exclude_locally(root: Path) -> bool:
    """Hide .brain/ from git without touching .gitignore.

    .git/info/exclude is local-only and never committed, so opting a work repo in
    cannot put a private engineering note into someone else's diff.
    """
    exclude = root / ".git" / "info" / "exclude"
    if not exclude.parent.is_dir():
        return False
    try:
        current = exclude.read_text() if exclude.exists() else ""
        if any(line.strip() == ".brain/" for line in current.splitlines()):
            return True
        with exclude.open("a") as handle:
            handle.write("\n.brain/\n")
        return True
    except OSError:
        return False


def cmd_init(args, call_model=None) -> int:
    root = Path.cwd()
    brain = root / ".brain"

    for folder in ("rules", "gotchas", "map", "_receipts"):
        (brain / folder).mkdir(parents=True, exist_ok=True)

    config = brain / "config.yml"
    if not config.exists():
        config.write_text("paused: false\nauto_remedy: true\n")

    vault.ensure(brain)
    excluded = _exclude_locally(root)

    print("Created %s" % brain)
    print("  git: %s" % ("hidden via .git/info/exclude" if excluded else "not a git repo"))

    if args.bare:
        index.generate(brain)
        print("  bare init; no rules mined. Add rules to .brain/rules/ by hand.")
        return 0

    docs = []
    for name in BOOTSTRAP_SOURCES:
        path = root / name
        if path.is_file():
            try:
                docs.append("### %s\n\n%s" % (name, path.read_text()[:20000]))
            except OSError:
                continue

    if not docs:
        index.generate(brain)
        print("  no AGENTS.md/CLAUDE.md/README to mine. Brain is empty but live.")
        return 0

    print("  mining rules from: %s" % ", ".join(
        name for name in BOOTSTRAP_SOURCES if (root / name).is_file()
    ))

    prompt = _bootstrap_prompt(docs)
    model = call_model or distiller._claude
    response = model(prompt)
    index.generate(brain)

    # An empty response means the model was never reached - `claude` is not on PATH,
    # or not logged in, or the network is down. Saying "no rules found" there would be
    # a lie: it tells someone their docs are ruleless when the tool never even ran.
    if not str(response).strip():
        print("  could not reach the `claude` CLI, so no rules were mined.")
        print("  The brain is live and empty. Check `claude --version`, then run:")
        print("    brain init")
        return 0

    written = distiller.apply(brain, distiller.parse_response(response))
    index.generate(brain)

    if not written:
        print("  the model found nothing enforceable in these docs.")
        print("  The brain is live and empty; rules will appear as you correct the agent.")
        return 0

    for path in written:
        print("  + %s" % path)
    print("\nRules start as `warn` and earn the right to block. Run `brain status`.")
    return 0


def _bootstrap_prompt(docs) -> str:
    return "\n\n".join([
        "This repo already documents how to work in it. Those documents are where good "
        "rules go to be ignored: an agent reads them, understands them, and does the "
        "wrong thing anyway forty tool calls later.",
        "Turn the ENFORCEABLE ones into rules a hook can actually check, and the "
        "hard-won facts into gotchas.",
        distiller.SCHEMA,
        "Rules only for things that can be mechanically checked at a tool call: "
        "'always run X before committing', 'never use Y', 'rebuild Z after touching W'. "
        "Style advice is not a rule. Be conservative; a handful of real rules beats "
        "twenty invented ones.",
        "Write gotchas/<name>.md for facts that cost someone time but cannot be "
        "enforced. Give each a `summary:` frontmatter line of under 60 characters.",
        "\n\n".join(docs),
        'Reply with ONLY a JSON array: [{"path": "rules/x.md", "content": "..."}]',
    ])


def cmd_status(args) -> int:
    brain = _brain_or_die()
    rules = load_rules(brain)

    print("brain: %s" % brain)
    print("state: %s" % ("PAUSED" if is_disabled(brain) else "active"))

    destination = mirror.target(brain)
    print("mirror: %s" % (destination or "off"))
    print()

    if not rules:
        print("No rules yet. Correct the agent and one will appear.")
    else:
        print("RULES")
        for rule in rules:
            verdict = ""
            if rule.overridden >= 2:
                verdict = "  <- being overridden; close to archiving"
            elif rule.satisfied >= 3 and rule.overridden == 0:
                verdict = "  <- earning its keep"
            print("  [%s] %-28s fired %d  satisfied %d  overridden %d%s" % (
                rule.severity, rule.id, rule.fired, rule.satisfied, rule.overridden, verdict
            ))

    archive = brain / "_archive"
    dead = list(archive.glob("*.md")) if archive.is_dir() else []
    if dead:
        print("\nARCHIVED (retired for being wrong)")
        for path in dead:
            print("  %s" % path.stem)

    pending = queue.peek(brain, "corrections")
    if pending:
        print("\nQUEUED CORRECTIONS (become rules at session end)")
        for item in pending:
            print("  %s" % str(item.get("prompt", ""))[:70])
    return 0


def cmd_why(args) -> int:
    brain = _brain_or_die()
    for rule in load_rules(brain):
        if rule.id == args.rule_id:
            print(rule.path.read_text())
            print("-" * 60)
            print("fired %d, satisfied %d, overridden %d" % (
                rule.fired, rule.satisfied, rule.overridden))
            if rule.overridden >= 2:
                print("This rule is close to archiving itself. It keeps being wrong.")
            elif rule.satisfied >= 3 and rule.overridden == 0:
                print("This rule is earning its keep.")
            return 0

    archived = brain / "_archive" / (args.rule_id + ".md")
    if archived.is_file():
        print(archived.read_text())
        return 0

    print("No rule '%s'." % args.rule_id)
    return 1


def cmd_check(args) -> int:
    brain = _brain_or_die()
    root = repo_root(brain)
    tool_input = {"command": args.cmd}

    decision = decide(
        load_rules(brain),
        args.tool,
        args.cmd,
        tool_input,
        is_fresh_fn=lambda r: receipts.is_fresh(brain, "cli-check", r.receipt, r.fresher_than, root),
        was_denied_fn=lambda r: False,
        auto_remedy=False,
    )

    print("tool:    %s" % args.tool)
    print("command: %s" % args.cmd)
    print("action:  %s" % decision.action.upper())
    if decision.rule:
        print("rule:    %s" % decision.rule.id)
    if decision.reason:
        print()
        print(decision.reason)
    if decision.action == "allow" and decision.rule is None:
        print("\nNo rule gates this command right now.")
    return 0


def cmd_doctor(args) -> int:
    brain = find_brain(Path.cwd())
    print("python:        %s" % sys.version.split()[0])
    print("brain here:    %s" % (brain or "none (this repo is untouched)"))
    print("global pause:  %s" % (Path.home() / ".brain" / "DISABLED").exists())

    if brain is None:
        print("\nEvery hook is a no-op in this repo. Run `brain init` to opt in.")
        return 0

    print("repo paused:   %s" % is_disabled(brain))
    print("auto_remedy:   %s" % get(brain, "auto_remedy", "true"))
    print("mirror:        %s" % (mirror.target(brain) or "off"))
    print("rules:         %d" % len(load_rules(brain)))

    errors = brain / "_log" / "hook-errors.log"
    if errors.is_file():
        lines = errors.read_text().splitlines()[-5:]
        print("\nRECENT HOOK ERRORS")
        for line in lines:
            print("  %s" % line)
    else:
        print("hook errors:   none")
    return 0


def cmd_pause(args) -> int:
    if args.globally:
        flag = Path.home() / ".brain" / "DISABLED"
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("")
        print("Paused everywhere. `brain resume --global` to undo.")
        return 0

    brain = _brain_or_die()
    config = brain / "config.yml"
    text = config.read_text() if config.exists() else ""
    lines = [line for line in text.splitlines() if not line.strip().startswith("paused:")]
    lines.insert(0, "paused: true")
    config.write_text("\n".join(lines) + "\n")
    print("Paused in this repo.")
    return 0


def cmd_resume(args) -> int:
    if args.globally:
        flag = Path.home() / ".brain" / "DISABLED"
        if flag.exists():
            flag.unlink()
        print("Resumed everywhere.")
        return 0

    brain = _brain_or_die()
    config = brain / "config.yml"
    text = config.read_text() if config.exists() else ""
    lines = [line for line in text.splitlines() if not line.strip().startswith("paused:")]
    lines.insert(0, "paused: false")
    config.write_text("\n".join(lines) + "\n")
    print("Resumed in this repo.")
    return 0


def cmd_remember(args) -> int:
    brain = _brain_or_die()
    queue.push(brain, "corrections", {"prompt": args.text, "session": "explicit"})
    print("Noted. It becomes a rule or a gotcha at the end of this session.")
    return 0


def cmd_mirror(args) -> int:
    brain = _brain_or_die()
    destination = mirror.target(brain)
    if destination is None:
        print("No mirror configured.")
        print("Set one in ~/.brain/config.yml to mirror every repo:")
        print("  mirror: ~/path/to/your/vault")
        return 1
    count = mirror.export(brain, repo_root(brain).name)
    print("Exported %d files to %s/%s" % (count, destination, repo_root(brain).name))
    return 0


def cmd_dash(args) -> int:
    from hookkit import dash

    brain = _brain_or_die()
    name = repo_root(brain).name
    server, url, _ = dash.serve(brain, name, port=args.port, open_browser=not args.no_open)

    rules = load_rules(brain)
    dying = [r.id for r in rules if r.overridden >= 2]

    print("brain dash for %s" % name)
    print("  %s" % url)
    print("  %d rules, %d in trouble%s" % (
        len(rules), len(dying), (": " + ", ".join(dying)) if dying else ""
    ))
    print("\nCtrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.server_close()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="brain", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a brain and mine rules from the repo's docs")
    init.add_argument("--bare", action="store_true", help="do not mine rules from docs")
    init.set_defaults(func=cmd_init)

    sub.add_parser("status", help="what this brain knows").set_defaults(func=cmd_status)

    why = sub.add_parser("why", help="where a rule came from")
    why.add_argument("rule_id")
    why.set_defaults(func=cmd_why)

    check = sub.add_parser("check", help="dry-fire the gate, with no session")
    check.add_argument("--tool", default="Bash")
    check.add_argument("--cmd", required=True)
    check.set_defaults(func=cmd_check)

    sub.add_parser("doctor", help="what is installed and what is failing").set_defaults(func=cmd_doctor)

    pause = sub.add_parser("pause", help="stop enforcing")
    pause.add_argument("--global", dest="globally", action="store_true")
    pause.set_defaults(func=cmd_pause)

    resume = sub.add_parser("resume", help="start enforcing again")
    resume.add_argument("--global", dest="globally", action="store_true")
    resume.set_defaults(func=cmd_resume)

    remember = sub.add_parser("remember", help="write something down")
    remember.add_argument("text")
    remember.set_defaults(func=cmd_remember)

    sub.add_parser("mirror", help="export to the configured vault now").set_defaults(func=cmd_mirror)

    dash = sub.add_parser("dash", help="open a graph view of this repo's brain")
    dash.add_argument("--port", type=int, default=7373)
    dash.add_argument("--no-open", action="store_true", help="print the URL, do not open a browser")
    dash.set_defaults(func=cmd_dash)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
