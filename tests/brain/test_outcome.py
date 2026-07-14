"""The failure-safe rule for reading a Bash result.

Only a POSITIVELY CONFIRMED success counts as a pass. Anything ambiguous counts as
a failure, because the two errors are not symmetric:

  wrongly "passed" -> a passing receipt for a broken run -> the gate lets a bad
                      commit through. Silent and catastrophic.
  wrongly "failed" -> the gate re-runs the remedy. Wasteful and harmless.

So the emitter must never invent a pass, even if the payload shape changes.
"""

from hookkit.outcome import passed


def test_explicit_zero_exit_code_is_a_pass():
    assert passed({"tool_response": {"exit_code": 0}}) is True


def test_explicit_nonzero_exit_code_is_a_failure():
    assert passed({"tool_response": {"exit_code": 1}}) is False
    assert passed({"tool_response": {"exit_code": 127}}) is False


def test_is_error_false_is_a_pass():
    assert passed({"tool_response": {"is_error": False}}) is True


def test_is_error_true_is_a_failure():
    assert passed({"tool_response": {"is_error": True}}) is False


def test_exit_code_wins_over_is_error():
    assert passed({"tool_response": {"exit_code": 1, "is_error": False}}) is False


def test_interrupted_is_a_failure():
    assert passed({"tool_response": {"exit_code": 0, "interrupted": True}}) is False


def test_top_level_is_error_is_honoured():
    assert passed({"tool_response": {}, "is_error": True}) is False


def test_missing_tool_response_is_not_a_pass():
    assert passed({}) is False


def test_empty_tool_response_is_not_a_pass():
    """The critical case: an unrecognised shape must NEVER be read as success."""
    assert passed({"tool_response": {}}) is False


def test_unrecognised_shape_is_not_a_pass():
    assert passed({"tool_response": {"someFutureField": "whatever"}}) is False


def test_string_tool_response_is_not_a_pass():
    assert passed({"tool_response": "raw output text"}) is False


def test_garbage_is_not_a_pass():
    assert passed(None) is False
    assert passed({"tool_response": None}) is False
