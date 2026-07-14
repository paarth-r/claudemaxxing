import json

from hookkit.protocol import allow, command_of, deny, emit


def test_allow_has_no_decision_reason_when_silent():
    payload = allow()
    output = payload["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "allow"
    assert "additionalContext" not in output


def test_allow_can_inject_context():
    payload = allow("heads up: remedy timed out")
    output = payload["hookSpecificOutput"]
    assert output["permissionDecision"] == "allow"
    assert output["additionalContext"] == "heads up: remedy timed out"


def test_deny_carries_a_reason_the_agent_reads():
    payload = deny("no fresh live-run receipt")
    output = payload["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"] == "no fresh live-run receipt"


def test_emit_prints_json(capsys):
    emit(allow())
    captured = json.loads(capsys.readouterr().out)
    assert captured["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_emit_none_prints_nothing(capsys):
    emit(None)
    assert capsys.readouterr().out == ""


def test_command_of_reads_bash_command():
    assert command_of({"command": "git commit -m x"}) == "git commit -m x"


def test_command_of_is_empty_for_non_bash():
    assert command_of({"file_path": "/tmp/x"}) == ""


def test_command_of_survives_garbage():
    assert command_of(None) == ""
