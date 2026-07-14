"""Did a tool call actually succeed?

This is the most safety-critical judgement in the codebase, and the answer is not
where you would expect it to be.

Bash's `tool_response` contains `stdout`, `stderr`, `interrupted`, and `isImage`.
It does NOT contain an exit code, and it does NOT contain an error flag. Success is
signalled by WHICH EVENT FIRED:

    PostToolUse         -> the tool call succeeded
    PostToolUseFailure  -> the tool call failed (carries `error`, a string)

So both events must be registered, and the event name is the signal. Guessing at a
`tool_response.exit_code` here silently marks every command a failure - the receipt
is never earned, and the gate denies forever.

Everything unrecognised is treated as a failure, because the two mistakes are wildly
asymmetric:

  Reading a FAILURE as a pass  -> a passing receipt for a run that broke. The gate
                                  lets the commit through and the whole system
                                  becomes theatre. Catastrophic and silent.

  Reading a PASS as a failure  -> the gate asks for the run again. Harmless.
"""

from __future__ import annotations

SUCCESS_EVENT = "PostToolUse"
FAILURE_EVENT = "PostToolUseFailure"


def passed(payload) -> bool:
    """True only if this tool call is confirmed to have succeeded."""
    if not isinstance(payload, dict):
        return False

    response = payload.get("tool_response")

    # An interrupted command never counts, whatever else it claims.
    if isinstance(response, dict) and response.get("interrupted") is True:
        return False
    if payload.get("is_interrupt") is True:
        return False

    # If a real numeric exit code ever appears in the payload, it is authoritative.
    # Not documented for Bash today; honoured defensively if the schema grows one.
    if isinstance(response, dict):
        code = response.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            return code == 0

    event = payload.get("hook_event_name")
    if event == FAILURE_EVENT:
        return False

    # A genuine success payload always carries a tool_response object. Requiring one
    # keeps a malformed payload from being read as a pass just because the event name
    # looked right.
    if event == SUCCESS_EVENT and isinstance(response, dict):
        return True

    # Unrecognised event or malformed payload. Refuse to guess: not a pass.
    return False
