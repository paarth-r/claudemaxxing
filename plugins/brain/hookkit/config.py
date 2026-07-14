"""Config in three layers: repo, then machine, then built-in default.

    1. .brain/config.yml        this repo          highest priority
    2. ~/.brain/config.yml      this machine       the user-level default
    3. the passed default       built-in           what a stranger gets

This layering is the whole reason the tool can be both shipped and personal. Vault
mirroring is OFF in the box: a stranger never creates ~/.brain/config.yml, so the
brain never writes a single byte outside their repo and Obsidian is never mentioned.
Set the machine-level file once and every repo mirrors automatically, with no
per-repo setup and nothing personal hardcoded in the source.

Same flat `key: value` format as everything else - no YAML dependency.
"""

from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> dict:
    try:
        text = path.read_text()
    except OSError:
        return {}

    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        value = value.strip()
        if not value:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _machine() -> dict:
    try:
        return _read(Path.home() / ".brain" / "config.yml")
    except (OSError, RuntimeError):
        return {}


def get(brain, key: str, default=None):
    """Resolve a config value: repo, then machine, then the default."""
    if brain is not None:
        repo_values = _read(Path(brain) / "config.yml")
        if key in repo_values:
            return repo_values[key]

    machine_values = _machine()
    if key in machine_values:
        return machine_values[key]

    return default


def flag(brain, key: str, default: bool) -> bool:
    """The boolean form."""
    value = get(brain, key)
    if value is None:
        return default
    return str(value).strip().lower() == "true"
