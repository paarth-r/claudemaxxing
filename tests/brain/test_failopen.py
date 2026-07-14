import json
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _run(body: str, stdin: str) -> subprocess.CompletedProcess:
    """Run a hook script body in a subprocess so we can observe its real exit code."""
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(REPO / "plugins" / "brain")!r})
        from hookkit.failopen import run_hook
        """
    ) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_clean_hook_exits_zero():
    result = _run('run_hook(lambda payload: print("ok"))', json.dumps({"cwd": "/tmp"}))
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_raising_hook_still_exits_zero():
    result = _run(
        'def boom(payload):\n    raise RuntimeError("kaboom")\nrun_hook(boom)',
        json.dumps({"cwd": "/tmp"}),
    )
    assert result.returncode == 0, "a crashing hook must never block a tool call"
    assert "kaboom" in result.stderr


def test_malformed_stdin_exits_zero():
    result = _run('run_hook(lambda payload: print("ok"))', "this is not json")
    assert result.returncode == 0


def test_empty_stdin_exits_zero():
    result = _run('run_hook(lambda payload: print("ok"))', "")
    assert result.returncode == 0


def test_payload_is_passed_through():
    result = _run(
        'run_hook(lambda payload: print(payload["cwd"]))',
        json.dumps({"cwd": "/some/project"}),
    )
    assert result.returncode == 0
    assert "/some/project" in result.stdout
