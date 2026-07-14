"""Rules must be able to die.

The moment a model writes its own enforcement, rules appear that no human approved.
The safety valve is that a rule carries its own evidence and is judged by it: one
that keeps being overridden is, by construction, one that keeps being wrong, and it
archives itself without the user ever having to file a bug against their own memory.
"""

from hookkit.lifecycle import ARCHIVE, DEMOTE, KEEP, PROMOTE, apply, review
from hookkit.rules import load_rules

RULE = """---
id: live-run-before-commit
severity: {severity}
trigger.tool: Bash
trigger.pattern: ^git commit
satisfied_by.receipt: live-run
stats.fired: {fired}
stats.satisfied: {satisfied}
stats.overridden: {overridden}
---

# Live run before commit

Body text.
"""


def _install(repo, severity="warn", fired=0, satisfied=0, overridden=0):
    (repo / ".brain" / "rules" / "live-run.md").write_text(
        RULE.format(severity=severity, fired=fired, satisfied=satisfied, overridden=overridden)
    )
    return load_rules(repo / ".brain")[0]


def test_a_fresh_rule_is_kept(repo):
    assert review(_install(repo)) == KEEP


def test_three_overrides_archives_the_rule(repo):
    rule = _install(repo, overridden=3)
    assert review(rule) == ARCHIVE


def test_a_block_rule_demotes_on_its_first_override(repo):
    rule = _install(repo, severity="block", overridden=1)
    assert review(rule) == DEMOTE


def test_a_warn_rule_that_keeps_passing_promotes(repo):
    rule = _install(repo, severity="warn", satisfied=5, overridden=0)
    assert review(rule) == PROMOTE


def test_a_rule_with_overrides_never_promotes(repo):
    rule = _install(repo, severity="warn", satisfied=10, overridden=1)
    assert review(rule) != PROMOTE


def test_an_already_blocking_rule_does_not_re_promote(repo):
    rule = _install(repo, severity="block", satisfied=10, overridden=0)
    assert review(rule) == KEEP


def test_archive_wins_over_demote(repo):
    """Three overrides on a blocking rule kills it rather than merely demoting it."""
    rule = _install(repo, severity="block", overridden=3)
    assert review(rule) == ARCHIVE


def test_apply_promote_rewrites_severity(repo):
    rule = _install(repo, severity="warn", satisfied=5)
    apply(rule, repo / ".brain")
    assert "severity: block" in rule.path.read_text()


def test_apply_demote_rewrites_severity(repo):
    rule = _install(repo, severity="block", overridden=1)
    apply(rule, repo / ".brain")
    assert "severity: warn" in rule.path.read_text()


def test_apply_archive_moves_the_file_out_of_rules(repo):
    rule = _install(repo, overridden=3)
    apply(rule, repo / ".brain")
    assert not rule.path.exists(), "an archived rule must stop being enforced"
    assert (repo / ".brain" / "_archive" / "live-run.md").exists()
    assert load_rules(repo / ".brain") == []


def test_archived_rule_explains_why_it_died(repo):
    rule = _install(repo, overridden=3)
    apply(rule, repo / ".brain")
    text = (repo / ".brain" / "_archive" / "live-run.md").read_text()
    assert "overridden 3" in text.lower() or "3 override" in text.lower()
    assert "Body text." in text, "the original content must survive archiving"


def test_apply_keep_changes_nothing(repo):
    rule = _install(repo)
    before = rule.path.read_text()
    apply(rule, repo / ".brain")
    assert rule.path.read_text() == before


def test_apply_on_a_missing_file_is_a_silent_no_op(repo):
    rule = _install(repo, overridden=3)
    rule.path.unlink()
    apply(rule, repo / ".brain")  # must not raise


def test_archive_does_not_clobber_an_existing_archived_file(repo):
    archive = repo / ".brain" / "_archive"
    archive.mkdir(parents=True)
    (archive / "live-run.md").write_text("an older archived rule\n")
    rule = _install(repo, overridden=3)
    apply(rule, repo / ".brain")
    survivors = sorted(p.name for p in archive.glob("*.md"))
    assert len(survivors) == 2, "archiving must not destroy earlier history"
