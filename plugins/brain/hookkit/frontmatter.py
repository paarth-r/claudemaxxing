"""A deliberately tiny frontmatter parser.

Rule files use FLAT DOTTED KEYS, never nested YAML:

    trigger.tool: Bash
    trigger.pattern: ^git (commit|push)
    remedy.timeout: 300

Two reasons. First, it means zero third-party dependencies: hooks run under
whatever python3 the user has, and we cannot assume pyyaml is installed. Second,
it is a stricter and more reproducible target for a model to emit than nested
YAML, and these files are machine-written.

Values run to end of line, so regexes and URLs containing ':' work unescaped.
"""

from __future__ import annotations


def _coerce(value: str):
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def parse(text: str):
    """Split a rule file into (meta, body). Malformed frontmatter yields ({}, text)."""
    if not text.startswith("---"):
        return {}, text

    lines = text.split("\n")
    close = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            close = index
            break

    if close is None:
        return {}, text

    meta = {}
    for raw in lines[1:close]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[key] = _coerce(value)

    body = "\n".join(lines[close + 1:]).lstrip("\n")
    return meta, body
