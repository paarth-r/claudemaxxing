"""Does this prompt look like the user correcting the agent?

That moment is the single highest-signal event in a session. "No, you have to live
run before you push" is not a task - it is a rule being stated out loud, usually for
the second or third time. Catching it is the whole point of the system.

This runs on EVERY prompt, so it must be free: a regex, no model call, no context
cost. It is a filter, not a judgement. The distiller decides what is actually a
rule; this only decides what is worth showing it. False positives cost nothing.
False negatives are the real loss, so it errs toward flagging.
"""

from __future__ import annotations

import re

# Prohibitions, imperatives, and reprimands. Word-bounded, so "notice" is not "no"
# and "nostalgic" is not "no".
PATTERNS = [
    r"\bno\b\s*[,.]",          # "no, you have to..." / "no. run it first."
    r"\bnever\b",
    r"\bdon'?t\b",
    r"\bdo not\b",
    r"\bstop\b",
    r"\balways\b",
    r"\byou (need|have) to\b",
    r"\byou should\b",
    r"\byou forgot\b",
    r"\bmake sure (you|to)\b",
    r"\bremember to\b",
    r"\bi (told|keep telling) you\b",
    r"\bagain\b.*\byou\b",
]

_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS]


def looks_like_correction(prompt) -> bool:
    """True if this prompt smells like a rule being stated rather than a task."""
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    return any(pattern.search(prompt) for pattern in _COMPILED)
