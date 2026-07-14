from pathlib import Path

from hookkit.gate import decide
from hookkit.rules import Rule


def make_rule(**overrides) -> Rule:
    defaults = dict(
        id="live-run-before-commit",
        path=Path("/tmp/live-run.md"),
        severity="warn",
        trigger_tool="Bash",
        trigger_pattern=r"^git (commit|push)",
        receipt="live-run",
        fresher_than="src/**",
        remedy_command="./run.sh --source videos/test.mp4",
        remedy_timeout=300,
        emits_pattern=r"^\./run\.sh",
        fired=0,
        satisfied=0,
        overridden=0,
    )
    defaults.update(overrides)
    return Rule(**defaults)


COMMIT = {"command": "git commit -m 'fix'"}


def never(rule):
    return False


def always(rule):
    return True


def test_no_rules_allows_silently():
    decision = decide([], "Bash", "git commit -m x", COMMIT, never, never, True)
    assert decision.action == "allow"
    assert decision.context == ""


def test_unmatched_command_allows_silently():
    decision = decide(
        [make_rule()], "Bash", "git status", {"command": "git status"}, never, never, True
    )
    assert decision.action == "allow"


def test_fresh_receipt_allows_silently():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, always, never, True)
    assert decision.action == "allow"
    assert decision.context == ""
    assert decision.rule is None


def test_stale_receipt_triggers_remedy_when_auto_remedy_on():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, never, True)
    assert decision.action == "remedy"
    assert decision.rule.id == "live-run-before-commit"


def test_stale_receipt_denies_when_auto_remedy_off():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, never, False)
    assert decision.action == "deny"
    assert "./run.sh --source videos/test.mp4" in decision.reason


def test_stale_receipt_denies_when_rule_has_no_remedy():
    rule = make_rule(remedy_command=None)
    decision = decide([rule], "Bash", "git commit -m x", COMMIT, never, never, True)
    assert decision.action == "deny"


def test_second_identical_attempt_is_released():
    """The anti-deadlock property: a wrong rule costs one turn, not a lockout."""
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, always, True)
    assert decision.action == "allow"
    assert decision.override is True
    assert decision.rule.id == "live-run-before-commit"
    assert "override" in decision.context.lower()


def test_release_happens_even_with_auto_remedy_off():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, always, False)
    assert decision.action == "allow"
    assert decision.override is True


def test_a_satisfied_rule_is_never_overridden():
    """Freshness is checked before denial history: a passing rule allows cleanly."""
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, always, always, True)
    assert decision.action == "allow"
    assert decision.override is False


def test_first_matching_rule_wins():
    first = make_rule(id="first", trigger_pattern=r"^git commit")
    second = make_rule(id="second", trigger_pattern=r"^git")
    decision = decide([first, second], "Bash", "git commit -m x", COMMIT, never, never, True)
    assert decision.rule.id == "first"


def test_deny_reason_names_the_rule_and_the_remedy():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, never, False)
    assert "live-run-before-commit" in decision.reason
    assert "./run.sh --source videos/test.mp4" in decision.reason


def test_deny_reason_tells_the_agent_how_to_get_unstuck():
    decision = decide([make_rule()], "Bash", "git commit -m x", COMMIT, never, never, False)
    assert "retry" in decision.reason.lower()


def test_different_tool_is_not_gated():
    decision = decide([make_rule()], "Write", "git commit -m x", COMMIT, never, never, True)
    assert decision.action == "allow"
