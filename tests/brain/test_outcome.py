"""How we know whether a Bash command actually succeeded.

Verified against the hook docs, not assumed. Bash's `tool_response` carries
`stdout`, `stderr`, `interrupted`, and `isImage` - there is NO `exit_code` and no
`is_error`. Success is signalled by WHICH EVENT FIRED:

    PostToolUse         -> the command succeeded
    PostToolUseFailure  -> the command failed

Everything else is treated as a failure, because the two mistakes are not
symmetric:

  wrongly "passed" -> a passing receipt for a broken run -> the gate lets a bad
                      commit through. Silent and catastrophic.
  wrongly "failed" -> the gate asks for the run again. Wasteful and harmless.
"""

from hookkit.outcome import passed

POST = "PostToolUse"
FAIL = "PostToolUseFailure"


def test_posttooluse_means_success():
    """The documented contract: this event only fires when the tool succeeded."""
    payload = {
        "hook_event_name": POST,
        "tool_response": {"stdout": "ok", "stderr": "", "interrupted": False, "isImage": False},
    }
    assert passed(payload) is True


def test_posttooluse_failure_event_means_failure():
    payload = {
        "hook_event_name": FAIL,
        "error": "Command exited with non-zero status code 1",
        "is_interrupt": False,
    }
    assert passed(payload) is False


def test_interrupted_command_is_never_a_pass():
    payload = {
        "hook_event_name": POST,
        "tool_response": {"stdout": "", "stderr": "", "interrupted": True},
    }
    assert passed(payload) is False


def test_real_bash_response_shape_with_no_exit_code_still_passes():
    """The exact shape the docs specify. An earlier version failed this outright."""
    payload = {
        "hook_event_name": POST,
        "tool_name": "Bash",
        "tool_input": {"command": "./run.sh"},
        "tool_response": {"stdout": "847 frames", "stderr": "", "interrupted": False, "isImage": False},
    }
    assert passed(payload) is True


def test_explicit_exit_code_is_honoured_if_it_ever_appears():
    """Future-proofing: a real numeric exit code, if present, is authoritative."""
    assert passed({"hook_event_name": POST, "tool_response": {"exit_code": 1}}) is False
    assert passed({"hook_event_name": POST, "tool_response": {"exit_code": 0}}) is True


def test_unknown_event_is_not_a_pass():
    assert passed({"hook_event_name": "SomethingElse", "tool_response": {}}) is False


def test_missing_event_is_not_a_pass():
    assert passed({"tool_response": {"stdout": "ok"}}) is False


def test_garbage_is_not_a_pass():
    assert passed(None) is False
    assert passed({}) is False
    assert passed({"hook_event_name": POST, "tool_response": None}) is False
