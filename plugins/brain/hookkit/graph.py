"""Turn a brain into a graph: nodes, edges, and each rule's track record.

This is not a neutral note graph. Obsidian already draws one of those. The thing
that is true about THIS vault and no other is that its rules carry evidence - fired,
satisfied, overridden - and they live or die by it. So the graph exports that
evidence, and the viewer draws it: a rule that keeps being overridden is visibly
dying, and one that earned the right to block is visibly solid.
"""

from __future__ import annotations

import re
from pathlib import Path

from hookkit.frontmatter import parse
from hookkit.lifecycle import ARCHIVE_AFTER, PROMOTE_AFTER
from hookkit.rules import load_rules

NOTE_DIRS = ("gotchas", "map", "utils", "notes")
WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def _links(body: str):
    """Wikilink targets, reduced to a bare stem: [[gotchas/mp4v|codec]] -> mp4v."""
    found = []
    for raw in WIKILINK.findall(body):
        stem = raw.strip().split("/")[-1].strip()
        if stem:
            found.append(stem)
    return found


def _health(rule) -> str:
    """What is happening to this rule right now, in one word."""
    if rule.overridden >= ARCHIVE_AFTER - 1:
        return "dying"
    if rule.overridden > 0:
        return "contested"
    if rule.severity == "block":
        return "enforced"
    if rule.satisfied >= PROMOTE_AFTER - 2:
        return "earning"
    return "learning"


def build(brain) -> dict:
    """Everything the viewer needs, as plain JSON-able data."""
    root = Path(brain)
    nodes = []
    edges = []
    by_stem = {}

    for rule in load_rules(root):
        try:
            _, body = parse(Path(rule.path).read_text())
        except OSError:
            body = ""

        stem = Path(rule.path).stem
        node = {
            "id": stem,
            "label": rule.id,
            "kind": "rule",
            "severity": rule.severity,
            "health": _health(rule),
            "fired": rule.fired,
            "satisfied": rule.satisfied,
            "overridden": rule.overridden,
            "strikes_left": max(0, ARCHIVE_AFTER - rule.overridden),
            "trigger": rule.trigger_pattern,
            "receipt": rule.receipt,
            "remedy": rule.remedy_command or "",
            "body": body.strip(),
        }
        nodes.append(node)
        by_stem[stem] = node
        for target in _links(body):
            edges.append({"source": stem, "target": target})

    for folder in NOTE_DIRS:
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                meta, body = parse(path.read_text())
            except OSError:
                continue
            summary = meta.get("summary")
            node = {
                "id": path.stem,
                "label": path.stem,
                "kind": "note",
                "folder": folder,
                "summary": str(summary).strip() if summary else "",
                "body": body.strip(),
            }
            nodes.append(node)
            by_stem[path.stem] = node
            for target in _links(body):
                edges.append({"source": path.stem, "target": target})

    archive = root / "_archive"
    if archive.is_dir():
        for path in sorted(archive.glob("*.md")):
            try:
                _, body = parse(path.read_text())
            except OSError:
                body = ""
            node = {
                "id": path.stem,
                "label": path.stem,
                "kind": "archived",
                "body": body.strip(),
            }
            nodes.append(node)
            by_stem.setdefault(path.stem, node)

    # Drop links that point nowhere. A dangling wikilink is a note not yet written,
    # not an edge.
    edges = [e for e in edges if e["target"] in by_stem and e["target"] != e["source"]]

    seen = set()
    unique = []
    for edge in edges:
        key = (edge["source"], edge["target"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)

    return {"nodes": nodes, "edges": unique}
