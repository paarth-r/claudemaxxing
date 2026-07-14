"""Two-scope kill switch.

Global:   ~/.brain/DISABLED     (a file; `touch` it and everything stops)
Per-repo: .brain/config.yml     (a line `paused: true`)

The global switch is a bare file check on purpose: it works even if every other
part of this codebase is broken.
"""

from __future__ import annotations

from pathlib import Path


def _global_disabled() -> bool:
    try:
        return (Path.home() / ".brain" / "DISABLED").exists()
    except (OSError, RuntimeError):
        return False


def config_flag(brain: Path, key: str, default: bool) -> bool:
    """Read a flat `key: true|false` line from .brain/config.yml."""
    config = Path(brain) / "config.yml"
    try:
        text = config.read_text()
    except OSError:
        return default

    for line in text.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip() == key:
            return value.strip().lower() == "true"
    return default


def is_disabled(brain: Path | None) -> bool:
    """True if the brain should do nothing at all right now."""
    if _global_disabled():
        return True
    if brain is None:
        return False
    return config_flag(brain, "paused", default=False)
