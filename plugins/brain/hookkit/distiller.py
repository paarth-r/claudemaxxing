"""Turn a session into rules and notes.

The only component that calls a model, and therefore the only one that handles
untrusted model output. Three properties are enforced here regardless of what the
model says:

  1. NOTHING is written outside .brain/. A model-authored path is untrusted input:
     `../../.ssh/authorized_keys` is a path a model can emit, so every path is
     resolved and checked against the brain root before a byte is written.

  2. The model NEVER sets its own enforcement level. Every new rule is rewritten to
     `severity: warn` on the way in. Rules earn the right to block by being right
     repeatedly (see lifecycle.py); they are never born with it.

  3. Nothing is lost on failure. Queues drain only after a successful write, so a
     model timeout means the corrections wait for the next session rather than
     evaporating.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from hookkit import queue

# The model may write knowledge. It may not forge receipts, and it may not resurrect
# rules that the lifecycle already retired.
PROTECTED = ("_receipts", "_archive", "_queue", "_log")

MAX_TRANSCRIPT_CHARS = 12000

SCHEMA = """A rule file is markdown with FLAT DOTTED frontmatter keys. No nesting, no lists.

---
id: <kebab-case-id>
severity: warn
trigger.tool: Bash
trigger.pattern: <regex matched against the command, e.g. ^git (commit|push)>
satisfied_by.receipt: <a name you choose, e.g. live-run>
satisfied_by.fresher_than: <optional glob; the receipt must be newer than these files, e.g. src/**>
remedy.command: <optional shell command that satisfies the rule; omit if it must not be auto-run>
remedy.timeout: 300
emits.pattern: <optional regex; commands matching this COUNT as producing the receipt>
stats.fired: 0
stats.satisfied: 0
stats.overridden: 0
---

# Title

Why this rule exists, in prose. State the cost of getting it wrong."""


def build_prompt(brain, corrections, pain, transcript_excerpt, existing_ids) -> str:
    parts = [
        "You maintain a project's engineering memory. Decide what, if anything, from "
        "this session is worth writing down so a future agent does not repeat it.",
        "",
        "Write two kinds of thing:",
        "  rules/    an ENFORCEABLE constraint. A hook will intercept a tool call and "
        "check it. Only write a rule if it can be mechanically checked.",
        "  gotchas/  a fact that cost someone time. Not enforceable, just true.",
        "",
        SCHEMA,
        "",
        "Hard requirements:",
        "- Be conservative. Writing nothing is a perfectly good outcome. Do not invent "
        "rules from a single ambiguous remark.",
        "- A rule must be mechanically checkable. 'Write clean code' is not a rule.",
        "- Prefer UPDATING an existing file over creating a near-duplicate.",
        "- severity is always `warn`. Rules earn the right to block by being right.",
        "",
    ]

    if existing_ids:
        parts += ["Rules that already exist (update these rather than duplicating):",
                  ", ".join(existing_ids), ""]

    if corrections:
        parts += ["The user CORRECTED the agent during this session. This is the highest",
                  "signal there is - a correction is usually a rule being restated for the",
                  "second or third time:"]
        for item in corrections:
            parts.append("  - " + str(item.get("prompt", ""))[:500])
        parts.append("")

    if pain:
        parts += ["Commands that FAILED during this session (a wall the agent hit; the",
                  "resolution is worth recording if you can infer it):"]
        for item in pain[:20]:
            parts.append("  - %s -> %s" % (
                str(item.get("cmd", ""))[:120], str(item.get("error", ""))[:160]
            ))
        parts.append("")

    if transcript_excerpt:
        parts += ["Session excerpt:", transcript_excerpt[:MAX_TRANSCRIPT_CHARS], ""]

    parts += [
        "Reply with ONLY a JSON array of files to write. No prose outside it.",
        '[{"path": "rules/live-run-before-commit.md", "content": "---\\nid: ...\\n---\\n\\n# ..."}]',
        "An empty array [] is a valid and often correct answer.",
    ]
    return "\n".join(parts)


def parse_response(text):
    """The model's file operations, or [] if it did not give us any."""
    if not isinstance(text, str) or not text.strip():
        return []

    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    blob = fenced.group(1) if fenced else None

    if blob is None:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        blob = text[start:end + 1]

    try:
        parsed = json.loads(blob)
    except ValueError:
        return []

    if not isinstance(parsed, list):
        return []

    ops = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        if isinstance(path, str) and isinstance(content, str) and path and content:
            ops.append({"path": path, "content": content})
    return ops


def _safe_target(brain: Path, raw: str):
    """Resolve a model-authored path, or None if it tries to escape the brain."""
    if raw.startswith("/") or raw.startswith("~"):
        return None

    root = Path(brain).resolve()
    try:
        target = (root / raw).resolve()
    except (OSError, ValueError, RuntimeError):
        return None

    try:
        relative = target.relative_to(root)
    except ValueError:
        return None  # escaped the brain

    if not relative.parts:
        return None
    if relative.parts[0] in PROTECTED:
        return None

    return target


def _force_warn(content: str) -> str:
    """A rule is born `warn`, whatever the model asked for."""
    if not content.startswith("---"):
        return content

    lines = content.split("\n")
    close = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            close = index
            break
    if close is None:
        return content

    for index in range(1, close):
        if lines[index].strip().startswith("severity:"):
            lines[index] = "severity: warn"
            return "\n".join(lines)

    lines.insert(1, "severity: warn")
    return "\n".join(lines)


def apply(brain: Path, ops):
    """Write the model's files. Returns the paths actually written."""
    written = []
    for op in ops:
        target = _safe_target(brain, op["path"])
        if target is None:
            continue

        content = op["content"]
        if op["path"].startswith("rules/"):
            content = _force_warn(content)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            written.append(op["path"])
        except OSError:
            continue
    return written


def _claude(prompt: str) -> str:
    """Headless Sonnet. Any failure returns empty, which writes nothing."""
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", "--model", "sonnet"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _excerpt(transcript_path):
    if not transcript_path:
        return ""
    try:
        lines = Path(transcript_path).read_text(errors="ignore").splitlines()
    except OSError:
        return ""

    turns = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        message = record.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            turns.append("%s: %s" % (message.get("role", "?"), content[:600]))
    return "\n".join(turns[-40:])


def run(brain: Path, session_id: str, transcript_path, call_model=_claude):
    """Distil this session into the brain. Returns the files written."""
    from hookkit.rules import load_rules

    corrections = queue.peek(brain, "corrections")
    pain = queue.peek(brain, "pain")
    excerpt = _excerpt(transcript_path)

    if not corrections and not pain and not excerpt:
        return []

    existing = [rule.id for rule in load_rules(brain)]
    prompt = build_prompt(brain, corrections, pain, excerpt, existing)

    try:
        response = call_model(prompt)
    except Exception:  # noqa: BLE001 - a distiller failure must never break SessionEnd
        return []

    written = apply(brain, parse_response(response))

    # Drain ONLY on success, so a failed distillation loses nothing.
    if written:
        queue.drain(brain, "corrections")
        queue.drain(brain, "pain")

    return written
