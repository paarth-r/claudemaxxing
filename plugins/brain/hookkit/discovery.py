"""Find the .brain/ directory for the repo a hook is firing in.

Repo-canonical storage means there is no registry and no mapping layer: the hook
runs with cwd inside the project, so it just walks up.
"""

# Hooks run under whatever bare `python3` the user has. On macOS that is still
# 3.9 (Xcode's), which has no `X | Y` union syntax. Keep annotations lazy.
from __future__ import annotations

from pathlib import Path


def find_brain(start) -> Path | None:
    """Walk up from `start` looking for a .brain directory. None if there isn't one."""
    try:
        current = Path(start).resolve()
    except (OSError, ValueError):
        return None

    if not current.exists():
        return None

    for directory in [current, *current.parents]:
        candidate = directory / ".brain"
        if candidate.is_dir():
            return candidate
    return None


def repo_root(brain: Path) -> Path:
    """The project directory that owns this .brain/."""
    return Path(brain).parent
