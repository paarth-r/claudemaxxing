"""Two-scope kill switch.

Global:   ~/.brain/DISABLED     (a file; `touch` it and everything stops)
Per-repo: .brain/config.yml     (a line `paused: true`)

The global switch is a bare file check on purpose: it works even if every other
part of this codebase is broken.
"""

from __future__ import annotations

from pathlib import Path

from hookkit.config import flag


def _global_disabled() -> bool:
    try:
        return (Path.home() / ".brain" / "DISABLED").exists()
    except (OSError, RuntimeError):
        return False


def config_flag(brain, key: str, default: bool) -> bool:
    """A boolean config value. Delegates to the layered reader so there is one
    config implementation, not two."""
    return flag(brain, key, default)


def is_disabled(brain) -> bool:
    """True if the brain should do nothing at all right now."""
    if _global_disabled():
        return True
    if brain is None:
        return False
    return config_flag(brain, "paused", default=False)
