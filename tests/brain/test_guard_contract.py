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

# The REAL Bash tool_response shape. No exit_code, no is_error - success is carried
# by which event fired. Getting this wrong marks every command a failure.
BASH_OK = {"stdout": "847 frames", "stderr": "", "interrupted": False, "isImage": False}


def _post(repo, command, event="PostToolUse", response=None, session="sess-1"):
    payload = {
        "session_id": session,
        "cwd": str(repo),
        "hook_event_name": event,
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if event == "PostToolUseFailure":
        payload["error"] = "Command exited with non-zero status code 1"
        payload["is_interrupt"] = False
    else:
        payload["tool_response"] = BASH_OK if response is None else response
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


def test_agent_run_command_earns_a_passing_receipt(repo):
    """With the REAL payload shape, which carries no exit code at all."""
    _install_rule(repo)
    _post(repo, "echo doing the live run")
    entries = _receipt_lines(repo)
    assert [e["kind"] for e in entries] == ["live-run"]
    assert entries[0]["exit"] == 0, "PostToolUse firing IS the success signal"


def test_failed_agent_run_earns_a_failing_receipt(repo):
    _install_rule(repo)
    _post(repo, "echo doing the live run", event="PostToolUseFailure")
    assert _receipt_lines(repo)[0]["exit"] == 1


def test_interrupted_run_is_not_a_pass(repo):
    _install_rule(repo)
    _post(repo, "echo doing the live run", response={"stdout": "", "interrupted": True})
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
    _post(repo, "echo live run", event="PostToolUseFailure")
    out = _fire(repo)
    assert out["permissionDecision"] == "deny", "a FAILED run must not satisfy the rule"


def test_no_brain_receipt_hook_is_a_no_op(bare_repo):
    payload = {
        "session_id": "s",
        "cwd": str(bare_repo),
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
        "tool_response": BASH_OK,
    }
    result = subprocess.run(
        [sys.executable, str(RECEIPT_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_a_persistently_wrong_rule_archives_itself(repo):
    """End to end: a rule the user keeps overriding stops existing.

    This is what makes it safe to let a model author its own enforcement. Three
    override strikes and the rule retires, with no human ever filing a bug against
    their own memory system.
    """
    _install_rule(repo, remedy="exit 1")

    for attempt in range(3):
        # Each round: a fresh command string, denied once, then released on retry.
        command = f"git commit -m attempt{attempt}"
        assert _fire(repo, command=command)["permissionDecision"] == "deny"
        assert _fire(repo, command=command)["permissionDecision"] == "allow"

    assert not (repo / ".brain" / "rules" / "live-run.md").exists(), "the rule must retire"
    archived = list((repo / ".brain" / "_archive").glob("*.md"))
    assert len(archived) == 1
    assert "overridden 3 times" in archived[0].read_text()

    # And it must genuinely stop enforcing.
    assert _fire(repo, command="git commit -m after") == {}, "an archived rule cannot gate"


CAPTURE_HOOK = PLUGIN / "scripts" / "capture.py"


def _prompt(repo, text, session="sess-1"):
    payload = {"session_id": session, "cwd": str(repo), "prompt": text}
    env = dict(os.environ)
    env["HOME"] = str(repo / "fakehome")
    result = subprocess.run(
        [sys.executable, str(CAPTURE_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    return result


def _queue(repo, kind):
    path = repo / ".brain" / "_queue" / f"{kind}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_a_correction_is_captured(repo):
    _prompt(repo, "no, you have to live run before you push")
    items = _queue(repo, "corrections")
    assert len(items) == 1
    assert "live run" in items[0]["prompt"]


def test_an_ordinary_prompt_is_not_captured(repo):
    _prompt(repo, "add a flag for the tracker")
    assert _queue(repo, "corrections") == []


def test_the_prompt_hook_prints_nothing(repo):
    """It fires on EVERY prompt. One token here is a tax on every turn, forever."""
    result = _prompt(repo, "no, you have to live run before you push")
    assert result.stdout == "", "UserPromptSubmit must never inject context"


def test_capture_is_a_no_op_without_a_brain(bare_repo):
    payload = {"session_id": "s", "cwd": str(bare_repo), "prompt": "never do that"}
    result = subprocess.run(
        [sys.executable, str(CAPTURE_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_a_failed_command_queues_pain(repo):
    _install_rule(repo)
    _post(repo, "npm run build", event="PostToolUseFailure")
    pain = _queue(repo, "pain")
    assert len(pain) == 1
    assert pain[0]["cmd"] == "npm run build"
    assert "non-zero" in pain[0]["error"]


def test_a_successful_command_queues_no_pain(repo):
    _install_rule(repo)
    _post(repo, "npm run build")
    assert _queue(repo, "pain") == []


DISTILL_HOOK = PLUGIN / "scripts" / "distill.py"


def test_the_full_loop_correction_becomes_an_enforced_rule(repo, monkeypatch):
    """The whole thesis, end to end, in one test.

    The user corrects the agent. The session ends. A rule the agent wrote itself now
    exists, and it gates the very command it was written about. Nobody edited a file.
    """
    from hookkit import distiller, queue
    from hookkit.rules import load_rules

    brain = repo / ".brain"

    # 1. The user corrects the agent mid-session. The hook queues it, silently.
    _prompt(repo, "no, you have to live run before you push")
    assert len(queue.peek(brain, "corrections")) == 1

    # 2. The session ends. The distiller asks a model what to write. (Stubbed: we are
    #    testing the plumbing, not the model.)
    authored = (
        "---\n"
        "id: live-run-before-commit\n"
        "severity: block\n"           # the model over-reaches; we must overrule it
        "trigger.tool: Bash\n"
        "trigger.pattern: ^git (commit|push)\n"
        "satisfied_by.receipt: live-run\n"
        "emits.pattern: ^\\./run\\.sh\n"
        "---\n\n"
        "# Live run before commit\n"
    )
    ops = json.dumps([{"path": "rules/live-run-before-commit.md", "content": authored}])
    written = distiller.run(brain, "sess-1", None, call_model=lambda _: ops)
    assert written == ["rules/live-run-before-commit.md"]

    # 3. The rule exists, and it was born `warn` no matter what the model asked for.
    rules = load_rules(brain)
    assert [r.id for r in rules] == ["live-run-before-commit"]
    assert rules[0].severity == "warn", "a model may not grant itself blocking power"

    # 4. The correction is consumed, not re-processed forever.
    assert queue.peek(brain, "corrections") == []

    # 5. And the rule the agent wrote actually gates the command it is about.
    out = _fire(repo, command="git push origin main")
    assert out["permissionDecision"] == "deny"
    assert "live-run-before-commit" in out["permissionDecisionReason"]
