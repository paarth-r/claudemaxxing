import json
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "brain"
CLI = PLUGIN / "cli.py"


def _run(cwd, *args, home=None):
    import os
    env = dict(os.environ)
    env["HOME"] = str(home or (cwd / "fakehome"))
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )


def _git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    return tmp_path


def test_init_creates_the_layout(tmp_path):
    _git_repo(tmp_path)
    result = _run(tmp_path, "init", "--bare")
    assert result.returncode == 0
    assert (tmp_path / ".brain" / "rules").is_dir()
    assert (tmp_path / ".brain" / "config.yml").is_file()
    assert (tmp_path / ".brain" / "index.md").is_file()


def test_init_makes_it_an_obsidian_vault(tmp_path):
    _git_repo(tmp_path)
    _run(tmp_path, "init", "--bare")
    assert (tmp_path / ".brain" / ".obsidian" / "app.json").is_file()


def test_init_hides_the_brain_from_git(tmp_path):
    """A work repo must never show .brain/ in its diff."""
    project = tmp_path / "project"
    project.mkdir()
    _git_repo(project)
    _run(project, "init", "--bare", home=tmp_path / "home")
    tmp_path = project
    exclude = (tmp_path / ".git" / "info" / "exclude").read_text()
    assert ".brain/" in exclude

    status = subprocess.run(
        ["git", "status", "--short"], cwd=str(tmp_path), capture_output=True, text=True
    )
    assert status.stdout.strip() == "", "the brain must be invisible to git"


def test_init_is_idempotent(tmp_path):
    _git_repo(tmp_path)
    _run(tmp_path, "init", "--bare")
    (tmp_path / ".brain" / "config.yml").write_text("paused: true\n")
    _run(tmp_path, "init", "--bare")
    assert "paused: true" in (tmp_path / ".brain" / "config.yml").read_text()
    exclude = (tmp_path / ".git" / "info" / "exclude").read_text()
    assert exclude.count(".brain/") == 1, "exclude must not accumulate duplicates"


def test_init_works_outside_a_git_repo(tmp_path):
    result = _run(tmp_path, "init", "--bare")
    assert result.returncode == 0
    assert "not a git repo" in result.stdout


def test_status_reports_rules(repo):
    (repo / ".brain" / "rules" / "r.md").write_text(
        "---\nid: live-run\nseverity: warn\ntrigger.tool: Bash\n"
        "trigger.pattern: ^git commit\nsatisfied_by.receipt: k\nstats.fired: 4\n---\n\n# R\n"
    )
    result = _run(repo, "status")
    assert result.returncode == 0
    assert "live-run" in result.stdout
    assert "fired 4" in result.stdout


def test_status_without_a_brain_exits_nonzero(bare_repo):
    result = _run(bare_repo, "status")
    assert result.returncode == 1
    assert "brain init" in result.stdout


def test_check_dry_fires_the_gate(repo):
    (repo / ".brain" / "rules" / "r.md").write_text(
        "---\nid: live-run\nseverity: warn\ntrigger.tool: Bash\n"
        "trigger.pattern: ^git (commit|push)\nsatisfied_by.receipt: live-run\n---\n\n# R\n"
    )
    result = _run(repo, "check", "--cmd", "git commit -m x")
    assert result.returncode == 0
    assert "DENY" in result.stdout
    assert "live-run" in result.stdout


def test_check_on_an_ungated_command(repo):
    result = _run(repo, "check", "--cmd", "ls")
    assert "ALLOW" in result.stdout
    assert "No rule gates this" in result.stdout


def test_why_prints_provenance(repo):
    (repo / ".brain" / "rules" / "r.md").write_text(
        "---\nid: live-run\nseverity: warn\ntrigger.tool: Bash\n"
        "trigger.pattern: ^git commit\nsatisfied_by.receipt: k\nstats.overridden: 2\n---\n\n"
        "# Live run\n\nBecause tests pass on green static.\n"
    )
    result = _run(repo, "why", "live-run")
    assert result.returncode == 0
    assert "green static" in result.stdout
    assert "close to archiving" in result.stdout


def test_why_on_an_unknown_rule(repo):
    result = _run(repo, "why", "nope")
    assert result.returncode == 1


def test_pause_and_resume(repo):
    _run(repo, "pause")
    assert "paused: true" in (repo / ".brain" / "config.yml").read_text()
    _run(repo, "resume")
    assert "paused: false" in (repo / ".brain" / "config.yml").read_text()


def test_global_pause_writes_the_flag(repo, tmp_path):
    home = tmp_path / "h"
    _run(repo, "pause", "--global", home=home)
    assert (home / ".brain" / "DISABLED").exists()
    _run(repo, "resume", "--global", home=home)
    assert not (home / ".brain" / "DISABLED").exists()


def test_doctor_reports_the_python_version(repo):
    result = _run(repo, "doctor")
    assert result.returncode == 0
    assert "python:" in result.stdout
    assert "rules:" in result.stdout


def test_doctor_in_an_unbrained_repo_says_so(bare_repo):
    result = _run(bare_repo, "doctor")
    assert result.returncode == 0
    assert "no-op" in result.stdout


def test_remember_queues_a_correction(repo):
    result = _run(repo, "remember", "never use mp4v")
    assert result.returncode == 0
    queued = (repo / ".brain" / "_queue" / "corrections.jsonl").read_text()
    assert "never use mp4v" in queued


def test_mirror_without_config_explains_how(repo, tmp_path):
    result = _run(repo, "mirror", home=tmp_path / "pristine")
    assert result.returncode == 1
    assert "~/.brain/config.yml" in result.stdout


def test_init_mines_rules_from_existing_docs(tmp_path, monkeypatch):
    """The bootstrap: a repo's own AGENTS.md becomes enforced rules on day one."""
    from cli import cmd_init

    _git_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text("Always run the tests before committing.\n")
    monkeypatch.chdir(tmp_path)

    authored = json.dumps([{
        "path": "rules/test-before-commit.md",
        "content": (
            "---\nid: test-before-commit\nseverity: block\ntrigger.tool: Bash\n"
            "trigger.pattern: ^git commit\nsatisfied_by.receipt: tests\n---\n\n# Tests\n"
        ),
    }])

    class Args:
        bare = False

    cmd_init(Args(), call_model=lambda _: authored)

    from hookkit.rules import load_rules
    rules = load_rules(tmp_path / ".brain")
    assert [r.id for r in rules] == ["test-before-commit"]
    assert rules[0].severity == "warn", "even a bootstrapped rule must be born warn"


def test_init_distinguishes_a_broken_model_from_ruleless_docs(tmp_path, monkeypatch, capsys):
    """If `claude` is missing or logged out, saying 'no rules found' is a LIE: it tells
    the user their docs are ruleless when the tool never ran at all."""
    from cli import cmd_init

    _git_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text("Always run make test before committing.\n")
    monkeypatch.chdir(tmp_path)

    class Args:
        bare = False

    cmd_init(Args(), call_model=lambda _: "")  # the model was never reached
    out = capsys.readouterr().out
    assert "could not reach" in out
    assert "may not contain" not in out


def test_init_reports_genuinely_ruleless_docs_differently(tmp_path, monkeypatch, capsys):
    from cli import cmd_init

    _git_repo(tmp_path)
    (tmp_path / "README.md").write_text("A library. No conventions here.\n")
    monkeypatch.chdir(tmp_path)

    class Args:
        bare = False

    cmd_init(Args(), call_model=lambda _: "[]")  # the model ran and found nothing
    out = capsys.readouterr().out
    assert "found nothing enforceable" in out
    assert "could not reach" not in out
