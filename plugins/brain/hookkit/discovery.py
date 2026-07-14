"""Find the .brain/ directory for the repo a hook is firing in.

Repo-canonical storage means there is no registry and no mapping layer: the hook
runs with cwd inside the project, so it just walks up.
"""

# Hooks run under whatever bare `python3` the user has. On macOS that is still
# 3.9 (Xcode's), which has no `X | Y` union syntax. Keep annotations lazy.
from __future__ import annotations

import subprocess
from pathlib import Path


def work_root(start, brain=None) -> Path:
    """The tree the code actually lives in RIGHT NOW - which is not always the tree
    that owns the brain.

    Git worktrees break the naive assumption. A worktree under .claude/worktrees/
    sits INSIDE the main checkout, so walking up finds the main tree's .brain/ - which
    is what we want, since a project should have one memory shared across its
    worktrees. But the code being committed lives in the WORKTREE.

    Get this wrong and the gate runs the test suite against the main checkout while
    you commit from a worktree: it tests the wrong code, passes, and writes a receipt
    saying your changes are fine. A silent false pass, which is the worst thing this
    system can do.

    So: the brain is found by walking up, but verification always runs against the
    git worktree the tool call came from.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass

    # Not a git repo, or git is unavailable: fall back to whoever owns the brain.
    if brain is not None:
        return repo_root(brain)
    return Path(start)


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
