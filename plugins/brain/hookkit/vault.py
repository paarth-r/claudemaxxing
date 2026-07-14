"""Make a brain directory openable as an Obsidian vault.

Obsidian will open any folder, but it keeps that vault's settings - graph layout,
hotkeys, appearance - in a `.obsidian/` directory INSIDE the folder. Two consequences
this module exists to handle:

  1. Seeding a minimal `.obsidian/` makes the folder open cleanly as a vault, with
     wikilinks resolving and the graph view working, instead of Obsidian treating it
     as an unconfigured directory.

  2. Anything that rewrites the folder MUST preserve `.obsidian/`, or the user's own
     vault settings are destroyed on every export. That is why `mirror.export` skips
     it rather than wiping the destination wholesale.

Both the repo's own .brain/ and any mirrored copy get this, so either can be opened
directly in Obsidian.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = ".obsidian"

# Wikilinks over markdown links, and no auto-created folders: the brain's layout is
# generated, and Obsidian should not invent directories inside it.
APP_JSON = {
    "useMarkdownLinks": False,
    "newLinkFormat": "shortest",
    "attachmentFolderPath": "./",
    "alwaysUpdateLinks": True,
}

CORE_PLUGINS = ["file-explorer", "global-search", "graph", "backlink", "outgoing-link", "tag-pane"]


def ensure(directory) -> bool:
    """Seed .obsidian/ so the folder opens as a vault. Never overwrites existing
    settings - the user's own vault config is theirs. Returns True if it seeded."""
    root = Path(directory)
    config = root / CONFIG_DIR

    if config.exists():
        return False  # already a vault; leave the user's settings alone

    try:
        config.mkdir(parents=True, exist_ok=True)
        (config / "app.json").write_text(json.dumps(APP_JSON, indent=2) + "\n")
        (config / "core-plugins.json").write_text(json.dumps(CORE_PLUGINS, indent=2) + "\n")
    except OSError:
        return False

    return True
