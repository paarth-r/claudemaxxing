"""Rewrite a single stats line in a rule file, in place.

The stats block is the evidence trail: it is how a rule proves it earns its keep,
and how a wrong rule proves it does not.
"""

from __future__ import annotations

import re
from pathlib import Path

from hookkit.rules import Rule

FIELDS = ("fired", "satisfied", "overridden")


def bump(rule: Rule, field: str) -> None:
    """Increment stats.<field> in the rule file. Silent no-op on any failure."""
    if field not in FIELDS:
        return

    path = Path(rule.path)
    try:
        text = path.read_text()
    except OSError:
        return

    key = "stats." + field
    pattern = re.compile(r"^" + re.escape(key) + r":\s*(\d+)\s*$", re.MULTILINE)
    match = pattern.search(text)

    if match:
        updated = pattern.sub(key + ": " + str(int(match.group(1)) + 1), text, count=1)
    else:
        # No stats line yet: insert one just before the closing frontmatter fence.
        lines = text.split("\n")
        close = None
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                close = index
                break
        if close is None:
            return
        lines.insert(close, key + ": 1")
        updated = "\n".join(lines)

    try:
        path.write_text(updated)
    except OSError:
        pass
