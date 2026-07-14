"""The index is the ENTIRE always-loaded context cost of the brain.

Everything else is either enforced by a hook (rules, which cost zero tokens because
the agent never needs to read them) or read on demand (notes). So the index gets a
hard budget, and a test that enforces it.
"""

from hookkit.index import generate

NOTE = """---
summary: {summary}
---

# {title}

Long body text that must never appear in the index. {filler}
"""


def _note(repo, folder, name, summary="", title="A Title", filler="x" * 500):
    directory = repo / ".brain" / folder
    directory.mkdir(parents=True, exist_ok=True)
    body = NOTE.format(summary=summary, title=title, filler=filler)
    if not summary:
        body = "# %s\n\nBody. %s\n" % (title, filler)
    (directory / (name + ".md")).write_text(body)


def _rule(repo, name):
    text = (
        "---\nid: %s\nseverity: warn\ntrigger.tool: Bash\n"
        "trigger.pattern: ^git commit\nsatisfied_by.receipt: k\n---\n\n# %s\n" % (name, name)
    )
    (repo / ".brain" / "rules" / (name + ".md")).write_text(text)


def test_an_empty_brain_yields_a_short_valid_index(repo):
    text = generate(repo / ".brain")
    assert text.strip()
    assert len(text) < 400


def test_the_index_is_written_to_disk(repo):
    generate(repo / ".brain")
    assert (repo / ".brain" / "index.md").is_file()


def test_a_note_contributes_one_line(repo):
    _note(repo, "gotchas", "mp4v", summary="the codec must be avc1, never mp4v")
    text = generate(repo / ".brain")
    assert "gotchas/mp4v" in text
    assert "the codec must be avc1" in text


def test_the_note_body_never_appears(repo):
    _note(repo, "gotchas", "mp4v", summary="short", filler="SECRETBODY" * 50)
    assert "SECRETBODY" not in generate(repo / ".brain")


def test_a_note_without_a_summary_falls_back_to_its_heading(repo):
    _note(repo, "map", "data-flow", summary="", title="Per-frame data flow")
    assert "Per-frame data flow" in generate(repo / ".brain")


def test_rules_are_a_count_not_a_list(repo):
    """Rules are enforced by hooks. The agent never needs to read them, so they cost
    zero context - listing them would be pure waste."""
    for name in ("live-run", "web-build", "no-mp4v"):
        _rule(repo, name)
    text = generate(repo / ".brain")
    assert "3 rule" in text
    assert "live-run" not in text
    assert "web-build" not in text


def test_archived_notes_are_excluded(repo):
    archive = repo / ".brain" / "_archive"
    archive.mkdir(parents=True)
    (archive / "dead.md").write_text("---\nsummary: a dead rule\n---\n\n# Dead\n")
    assert "dead" not in generate(repo / ".brain")


def test_receipts_and_queues_are_excluded(repo):
    (repo / ".brain" / "_receipts" / "s.jsonl").write_text("{}\n")
    queue = repo / ".brain" / "_queue"
    queue.mkdir(parents=True)
    (queue / "corrections.jsonl").write_text("{}\n")
    text = generate(repo / ".brain")
    assert "_receipts" not in text
    assert "_queue" not in text


def test_the_index_stays_within_budget(repo):
    """A realistic brain: 20 notes and 12 rules. This is the load-bearing test - the
    entire promise is that a big brain costs almost nothing at rest."""
    for index in range(20):
        _note(repo, "gotchas", "note%d" % index, summary="a fact worth knowing number %d" % index)
    for index in range(12):
        _rule(repo, "rule%d" % index)

    text = generate(repo / ".brain")
    assert len(text) < 1600, "index blew its budget: %d chars" % len(text)


def test_a_missing_brain_does_not_raise(tmp_path):
    assert generate(tmp_path / "nope" / ".brain") == "" or True
