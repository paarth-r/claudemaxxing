from hookkit.rules import emits, load_rules, matches

RULE = """---
id: live-run-before-commit
severity: warn
trigger.tool: Bash
trigger.pattern: ^git (commit|push)
satisfied_by.receipt: live-run
satisfied_by.fresher_than: src/**
remedy.command: ./run.sh --source videos/test.mp4
remedy.timeout: 300
emits.pattern: ^(\\./run\\.sh|uv run python main\\.py)
stats.fired: 2
stats.satisfied: 1
stats.overridden: 0
---

# Live run before commit
"""


def _write(repo, name, text):
    (repo / ".brain" / "rules" / name).write_text(text)


def test_loads_a_rule(repo):
    _write(repo, "live-run.md", RULE)
    rules = load_rules(repo / ".brain")
    assert len(rules) == 1
    assert rules[0].id == "live-run-before-commit"
    assert rules[0].remedy_timeout == 300
    assert rules[0].fresher_than == "src/**"


def test_no_rules_directory_returns_empty(tmp_path):
    assert load_rules(tmp_path / "nope" / ".brain") == []


def test_malformed_rule_is_skipped_not_raised(repo):
    _write(repo, "good.md", RULE)
    _write(repo, "bad.md", "---\nseverity: warn\n---\nno id, no trigger\n")
    rules = load_rules(repo / ".brain")
    assert [r.id for r in rules] == ["live-run-before-commit"]


def test_rule_with_bad_regex_is_skipped(repo):
    _write(repo, "bad.md", RULE.replace("^git (commit|push)", "^git ((("))
    assert load_rules(repo / ".brain") == []


def test_matches_the_triggering_command(repo):
    _write(repo, "live-run.md", RULE)
    rule = load_rules(repo / ".brain")[0]
    assert matches(rule, "Bash", "git commit -m 'fix'") is True
    assert matches(rule, "Bash", "git push origin main") is True


def test_does_not_match_unrelated_commands(repo):
    _write(repo, "live-run.md", RULE)
    rule = load_rules(repo / ".brain")[0]
    assert matches(rule, "Bash", "git status") is False
    assert matches(rule, "Bash", "ls") is False


def test_does_not_match_a_different_tool(repo):
    _write(repo, "live-run.md", RULE)
    rule = load_rules(repo / ".brain")[0]
    assert matches(rule, "Write", "git commit -m 'fix'") is False


def test_emits_recognises_a_satisfying_command(repo):
    _write(repo, "live-run.md", RULE)
    rule = load_rules(repo / ".brain")[0]
    assert emits(rule, "./run.sh --source videos/test.mp4") is True
    assert emits(rule, "uv run python main.py --source x.mp4") is True


def test_emits_false_for_unrelated_command(repo):
    _write(repo, "live-run.md", RULE)
    rule = load_rules(repo / ".brain")[0]
    assert emits(rule, "git status") is False


def test_emits_false_when_no_emits_pattern(repo):
    without = RULE.replace("emits.pattern: ^(\\./run\\.sh|uv run python main\\.py)\n", "")
    _write(repo, "live-run.md", without)
    rule = load_rules(repo / ".brain")[0]
    assert rule.emits_pattern is None
    assert emits(rule, "./run.sh") is False


def test_severity_defaults_to_warn(repo):
    _write(repo, "live-run.md", RULE.replace("severity: warn\n", ""))
    assert load_rules(repo / ".brain")[0].severity == "warn"
