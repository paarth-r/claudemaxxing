from hookkit.frontmatter import parse

SAMPLE = """---
id: live-run-before-commit
severity: warn
trigger.tool: Bash
trigger.pattern: ^git (commit|push)
satisfied_by.receipt: live-run
satisfied_by.fresher_than: src/**
remedy.timeout: 300
stats.fired: 3
enabled: true
---

# Live run before commit

Tests pass on code paths that render as green static.
"""


def test_parses_flat_keys():
    meta, _ = parse(SAMPLE)
    assert meta["id"] == "live-run-before-commit"
    assert meta["severity"] == "warn"


def test_parses_dotted_keys_literally():
    meta, _ = parse(SAMPLE)
    assert meta["trigger.tool"] == "Bash"
    assert meta["satisfied_by.receipt"] == "live-run"


def test_value_may_contain_colons_and_regex():
    meta, _ = parse(SAMPLE)
    assert meta["trigger.pattern"] == "^git (commit|push)"


def test_coerces_int():
    meta, _ = parse(SAMPLE)
    assert meta["remedy.timeout"] == 300
    assert meta["stats.fired"] == 3


def test_coerces_bool():
    meta, _ = parse(SAMPLE)
    assert meta["enabled"] is True


def test_returns_body_without_frontmatter():
    _, body = parse(SAMPLE)
    assert body.startswith("# Live run before commit")
    assert "severity" not in body


def test_no_frontmatter_returns_empty_meta():
    meta, body = parse("# just a note\n")
    assert meta == {}
    assert body == "# just a note\n"


def test_unterminated_frontmatter_returns_empty_meta():
    meta, _ = parse("---\nid: x\n\n# oops no close\n")
    assert meta == {}


def test_strips_surrounding_quotes():
    meta, _ = parse('---\ntrigger.pattern: "^git commit"\n---\nbody\n')
    assert meta["trigger.pattern"] == "^git commit"


def test_ignores_blank_and_comment_lines():
    meta, _ = parse("---\n\n# a comment\nid: x\n---\nbody\n")
    assert meta == {"id": "x"}


def test_a_value_with_a_url_keeps_its_colon():
    meta, _ = parse("---\nsee: https://example.com/x\n---\nbody\n")
    assert meta["see"] == "https://example.com/x"
