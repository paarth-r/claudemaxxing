"""Rules earn their enforcement, or they die.

This is the safety valve that makes it acceptable for a model to write its own
rules. A rule carries its own evidence in its `stats` block, and is judged by it:

  overridden >= 3                      -> ARCHIVE. It keeps being wrong.
  block, and overridden >= 1           -> DEMOTE. It lost the trust it had earned.
  warn, satisfied >= 5, no overrides   -> PROMOTE. It earned it.
  otherwise                            -> KEEP.

The thresholds are deliberately asymmetric. A wrongly-archived rule is cheap - the
next correction writes it again. A wrongly-enforced rule is expensive: the user has
to fight their own tools. So it is easy to lose enforcement and slow to gain it.

Nothing here can ever hard-fail: every filesystem error is swallowed.
"""

from __future__ import annotations

import re
from pathlib import Path

from hookkit.rules import Rule

KEEP = "keep"
PROMOTE = "promote"
DEMOTE = "demote"
ARCHIVE = "archive"

ARCHIVE_AFTER = 3       # overrides before a rule is retired outright
PROMOTE_AFTER = 5       # clean satisfactions before a warn rule starts blocking


def review(rule: Rule) -> str:
    """What should happen to this rule, given its own track record?"""
    if rule.overridden >= ARCHIVE_AFTER:
        return ARCHIVE

    if rule.severity == "block" and rule.overridden >= 1:
        return DEMOTE

    if rule.severity == "warn" and rule.satisfied >= PROMOTE_AFTER and rule.overridden == 0:
        return PROMOTE

    return KEEP


def _set_severity(path: Path, severity: str) -> None:
    try:
        text = path.read_text()
    except OSError:
        return

    pattern = re.compile(r"^severity:.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub("severity: " + severity, text, count=1)
    else:
        lines = text.split("\n")
        if lines and lines[0].strip() == "---":
            lines.insert(1, "severity: " + severity)
            text = "\n".join(lines)
        else:
            return

    try:
        path.write_text(text)
    except OSError:
        pass


def _unique(directory: Path, name: str) -> Path:
    """A free filename in `directory`. Archiving must never destroy earlier history."""
    candidate = directory / name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        alternative = directory / ("%s-%d%s" % (stem, index, suffix))
        if not alternative.exists():
            return alternative
    return directory / ("%s-last%s" % (stem, suffix))


def _archive(rule: Rule, brain: Path) -> None:
    path = Path(rule.path)
    try:
        text = path.read_text()
    except OSError:
        return

    note = (
        "\n\n---\n\n"
        "## Archived\n\n"
        "This rule was retired automatically after being overridden %d times. A rule "
        "that keeps getting overridden is a rule that keeps being wrong, so it stopped "
        "being enforced rather than continuing to cost a wasted turn on every commit.\n\n"
        "Fired %d times, satisfied %d. If it was right after all, move it back into "
        "rules/ and reset its stats.\n"
        % (rule.overridden, rule.fired, rule.satisfied)
    )

    directory = Path(brain) / "_archive"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _unique(directory, path.name).write_text(text + note)
        path.unlink()
    except OSError:
        pass


def apply(rule: Rule, brain: Path) -> str:
    """Act on the verdict. Returns the verdict. Never raises."""
    verdict = review(rule)

    if verdict == PROMOTE:
        _set_severity(Path(rule.path), "block")
    elif verdict == DEMOTE:
        _set_severity(Path(rule.path), "warn")
    elif verdict == ARCHIVE:
        _archive(rule, brain)

    return verdict
