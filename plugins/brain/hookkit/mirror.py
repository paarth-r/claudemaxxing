"""Optional one-way export of the brain to somewhere you can browse it.

OFF by default. With no `mirror` configured - which is what anyone installing this
gets - nothing is ever written outside the repo, and this module does nothing.

Point `mirror` at a folder (an Obsidian vault, a notes directory, anywhere) and the
brain is copied there on SessionEnd so you can read and graph it.

A COPY, never a symlink. Two reasons, both learned the hard way:
  - iCloud Drive mangles symlinks, dehydrating them into broken aliases.
  - A vault symlinked into a repo that later gets deleted leaves dead links behind.
A copy survives the repo being deleted, which is the entire point of having it.

One-way, always. Nothing is ever read back from the mirror; the repo is canonical.
Receipts and queues are never exported: they hold raw command lines and raw prompts.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hookkit import vault
from hookkit.config import get

# Machinery, not knowledge. Never leaves the repo.
PRIVATE = ("_receipts", "_queue", "_log")


def target(brain):
    """Where to export, or None if mirroring is not configured (the default)."""
    value = get(brain, "mirror")
    if not value or not str(value).strip():
        return None
    try:
        return Path(str(value)).expanduser()
    except (OSError, RuntimeError, ValueError):
        return None


def export(brain, repo_name: str) -> int:
    """Copy the brain's knowledge into <target>/<repo_name>/. Returns files written."""
    destination_root = target(brain)
    if destination_root is None:
        return 0

    source = Path(brain)
    destination = destination_root / repo_name

    try:
        destination.mkdir(parents=True, exist_ok=True)

        # Clear the content we manage so deletions propagate - an archived rule must
        # vanish from the vault rather than linger there as a ghost. But NEVER touch
        # .obsidian/: that is the user's own vault settings (graph layout, hotkeys,
        # appearance), and wiping it on every session would be vandalism.
        for existing in destination.iterdir():
            if existing.name == vault.CONFIG_DIR:
                continue
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
    except OSError:
        return 0

    count = 0
    try:
        for item in sorted(source.iterdir()):
            if item.name in PRIVATE or item.name.startswith("."):
                continue
            if item.is_dir():
                shutil.copytree(item, destination / item.name)
                count += sum(1 for p in (destination / item.name).rglob("*") if p.is_file())
            elif item.is_file():
                shutil.copy2(item, destination / item.name)
                count += 1
    except OSError:
        return count

    # Make the exported brain openable as a standalone Obsidian vault.
    vault.ensure(destination)

    return count
