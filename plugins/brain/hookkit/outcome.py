"""Did a tool call actually succeed?

This is the most safety-critical judgement in the codebase, and it is deliberately
paranoid.

The two possible mistakes are wildly asymmetric:

  Reading a FAILURE as a pass   -> we write a passing receipt for a run that broke.
                                   The gate then lets the commit through. The whole
                                   system silently becomes theatre. Catastrophic.

  Reading a PASS as a failure   -> the gate re-runs the remedy to check. Costs a few
                                   seconds. Harmless.

So: only a positively confirmed success counts. Every ambiguous, unrecognised, or
malformed payload is treated as a failure. This also means the emitter stays correct
if Claude Code changes the tool_response schema underneath us - it degrades to
"verify again", never to "assume it's fine".
"""

from __future__ import annotations


def passed(payload) -> bool:
    """True only if this tool call is confirmed to have succeeded."""
    if not isinstance(payload, dict):
        return False

    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return False

    # An interrupted command never counts, whatever else it claims.
    if response.get("interrupted") is True:
        return False

    if payload.get("is_error") is True:
        return False

    # Most specific signal first: a real exit code settles it either way.
    exit_code = response.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return exit_code == 0

    # Next: an explicit error flag.
    is_error = response.get("is_error")
    if isinstance(is_error, bool):
        return not is_error

    # Unrecognised shape. Refuse to guess: not a pass.
    return False
