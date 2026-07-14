import json
import os
import subprocess
import sys
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "brain"
GUARD = PLUGIN / "scripts" / "guard.py"

RULE = """---
id: live-run-before-commit
severity: warn
trigger.tool: Bash
trigger.pattern: ^git (commit|push)
satisfied_by.receipt: live-run
satisfied_by.fresher_than: src/**
remedy.command: {remedy}
remedy.timeout: 30
emits.pattern: ^echo
stats.fired: 0
stats.satisfied: 0
stats.overridden: 0
---

# Live run before commit
"""


def _fire(repo, command="git commit -m 'fix'", session="sess-1", home=None):
    payload = {
        "session_id": session,
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    env = dict(os.environ)
    env["HOME"] = str(home or (repo / "fakehome"))
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"guard must always exit 0, got {result.returncode}"
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)["hookSpecificOutput"]


def _install_rule(repo, remedy="echo ran"):
    (repo / ".brain" / "rules" / "live-run.md").write_text(RULE.format(remedy=remedy))


def test_no_brain_is_a_silent_no_op(bare_repo):
    payload = {
        "session_id": "s",
        "cwd": str(bare_repo),
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m x"},
    }
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "", "repos without .brain must be untouched"


def test_unrelated_command_passes_silently(repo):
    _install_rule(repo)
    assert _fire(repo, command="ls -la") == {}


def test_passing_remedy_allows_the_commit(repo):
    _install_rule(repo, remedy="echo ran")
    out = _fire(repo)
    assert out["permissionDecision"] == "allow"


def test_passing_remedy_writes_a_receipt(repo):
    _install_rule(repo, remedy="echo ran")
    _fire(repo)
    receipts = (repo / ".brain" / "_receipts" / "sess-1.jsonl").read_text()
    assert '"kind": "live-run"' in receipts
    assert '"exit": 0' in receipts


def test_failing_remedy_denies_with_the_real_error(repo):
    _install_rule(repo, remedy="echo boom >&2; exit 1")
    out = _fire(repo)
    assert out["permissionDecision"] == "deny"
    assert "boom" in out["permissionDecisionReason"]


def test_second_identical_attempt_is_released(repo):
    _install_rule(repo, remedy="exit 1")
    first = _fire(repo)
    assert first["permissionDecision"] == "deny"
    second = _fire(repo)
    assert second["permissionDecision"] == "allow", "the gate must never deadlock"
    assert "override" in second["additionalContext"].lower()


def test_override_is_recorded_in_the_rule_file(repo):
    _install_rule(repo, remedy="exit 1")
    _fire(repo)
    _fire(repo)
    text = (repo / ".brain" / "rules" / "live-run.md").read_text()
    assert "stats.overridden: 1" in text


def test_fired_is_recorded_in_the_rule_file(repo):
    _install_rule(repo, remedy="echo ran")
    _fire(repo)
    text = (repo / ".brain" / "rules" / "live-run.md").read_text()
    assert "stats.fired: 1" in text
    assert "stats.satisfied: 1" in text


def test_fresh_receipt_skips_the_remedy_entirely(repo):
    _install_rule(repo, remedy="exit 1")  # would deny if it ever ran
    old = time.time() - 100
    os.utime(repo / "src" / "main.py", (old, old))
    receipts = repo / ".brain" / "_receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    entry = {"kind": "live-run", "ts": time.time(), "cmd": "./run.sh", "exit": 0}
    (receipts / "sess-1.jsonl").write_text(json.dumps(entry) + "\n")
    assert _fire(repo) == {}, "a satisfied rule must pass silently"


def test_global_kill_switch_disables_everything(repo):
    _install_rule(repo, remedy="exit 1")
    home = repo / "fakehome"
    (home / ".brain").mkdir(parents=True)
    (home / ".brain" / "DISABLED").write_text("")
    assert _fire(repo, home=home) == {}, "the kill switch must make the gate silent"


def test_paused_repo_disables_the_gate(repo):
    _install_rule(repo, remedy="exit 1")
    (repo / ".brain" / "config.yml").write_text("paused: true\n")
    assert _fire(repo) == {}


def test_auto_remedy_off_denies_without_running_anything(repo):
    _install_rule(repo, remedy="echo ran")
    (repo / ".brain" / "config.yml").write_text("paused: false\nauto_remedy: false\n")
    out = _fire(repo)
    assert out["permissionDecision"] == "deny"
    assert "echo ran" in out["permissionDecisionReason"]


def test_corrupt_rule_file_does_not_break_the_gate(repo):
    _install_rule(repo, remedy="echo ran")
    (repo / ".brain" / "rules" / "junk.md").write_text("---\nnot: a rule\n---\n")
    out = _fire(repo)
    assert out["permissionDecision"] == "allow"


def test_a_stale_receipt_does_not_satisfy_the_gate(repo):
    """The property the whole design rests on, proved end to end through the hook."""
    _install_rule(repo, remedy="exit 1")  # remedy fails, so a stale pass would show
    receipts = repo / ".brain" / "_receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    entry = {"kind": "live-run", "ts": time.time(), "cmd": "./run.sh", "exit": 0}
    (receipts / "sess-1.jsonl").write_text(json.dumps(entry) + "\n")
    future = time.time() + 10
    os.utime(repo / "src" / "main.py", (future, future))  # edited AFTER the run
    out = _fire(repo)
    assert out["permissionDecision"] == "deny", "a run predating the edit must not count"


RECEIPT_HOOK = PLUGIN / "scripts" / "receipt.py"


def _post(repo, command, response=None, session="sess-1"):
    payload = {
        "session_id": session,
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": 0} if response is None else response,
    }
    env = dict(os.environ)
    env["HOME"] = str(repo / "fakehome")
    result = subprocess.run(
        [sys.executable, str(RECEIPT_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    return result


def _receipt_lines(repo, session="sess-1"):
    path = repo / ".brain" / "_receipts" / f"{session}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_agent_run_command_earns_a_receipt(repo):
    _install_rule(repo)
    _post(repo, "echo doing the live run")
    kinds = [r["kind"] for r in _receipt_lines(repo)]
    assert "live-run" in kinds


def test_failed_agent_run_earns_a_failing_receipt(repo):
    _install_rule(repo)
    _post(repo, "echo doing the live run", response={"exit_code": 1})
    assert _receipt_lines(repo)[0]["exit"] == 1


def test_unknown_response_shape_is_not_recorded_as_a_pass(repo):
    """Safety: an unrecognised payload must never mint a passing receipt."""
    _install_rule(repo)
    _post(repo, "echo doing the live run", response={"mystery": "future schema"})
    assert _receipt_lines(repo)[0]["exit"] == 1


def test_unrelated_command_earns_nothing(repo):
    _install_rule(repo)
    _post(repo, "git status")
    assert _receipt_lines(repo) == []


def test_agent_run_then_commit_sails_through(repo):
    """The happy path, end to end: do the work, then commit, and never see the gate."""
    _install_rule(repo, remedy="exit 1")  # the remedy would DENY if the gate ran it
    old = time.time() - 100
    os.utime(repo / "src" / "main.py", (old, old))
    _post(repo, "echo live run")
    assert _fire(repo) == {}, "a commit after a real live run must pass silently"


def test_failed_agent_run_does_not_let_the_commit_through(repo):
    _install_rule(repo, remedy="exit 1")
    old = time.time() - 100
    os.utime(repo / "src" / "main.py", (old, old))
    _post(repo, "echo live run", response={"exit_code": 1})
    out = _fire(repo)
    assert out["permissionDecision"] == "deny", "a FAILED run must not satisfy the rule"


def test_no_brain_receipt_hook_is_a_no_op(bare_repo):
    payload = {
        "session_id": "s",
        "cwd": str(bare_repo),
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
        "tool_response": {"exit_code": 0},
    }
    result = subprocess.run(
        [sys.executable, str(RECEIPT_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
