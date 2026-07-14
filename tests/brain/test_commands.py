"""Slash commands must actually appear in the / menu.

A skill is model-invoked; a command is user-typed and autocompletes. Shipping only a
skill is why `/brain` did not complete. These tests guard the things that make a
command discoverable, because a command with no description is a command nobody finds.
"""

from pathlib import Path

from hookkit.frontmatter import parse

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "brain"
COMMANDS = PLUGIN / "commands"

EXPECTED = {
    "status", "doctor", "check", "why", "remember", "dash", "init", "pause",
}

TAKES_ARGS = {"check", "why", "remember", "pause"}


def _files():
    return sorted(COMMANDS.glob("*.md"))


def test_the_commands_directory_exists():
    assert COMMANDS.is_dir(), "no commands/ means no autocomplete"


def test_every_expected_command_ships():
    assert {p.stem for p in _files()} == EXPECTED


def test_every_command_has_a_description():
    """The description is what the user reads in the / menu. Without one, the command
    is a name with no explanation."""
    for path in _files():
        meta, _ = parse(path.read_text())
        assert meta.get("description"), "%s has no description" % path.name


def test_descriptions_are_written_for_a_human_not_a_machine():
    """A description that names the implementation ('runs cli.py status') is useless in
    a menu. It should say what the user gets."""
    for path in _files():
        meta, _ = parse(path.read_text())
        description = str(meta["description"])
        assert len(description) > 20, "%s: too terse to be useful" % path.name
        assert "cli.py" not in description, "%s: describes the plumbing" % path.name


def test_commands_taking_arguments_hint_at_them():
    """argument-hint is what renders during autocomplete. Without it the user has to
    guess what to type after the command."""
    for path in _files():
        meta, _ = parse(path.read_text())
        if path.stem in TAKES_ARGS:
            assert meta.get("argument-hint"), "%s takes args but hints none" % path.name


def test_commands_that_run_shell_declare_bash():
    for path in _files():
        text = path.read_text()
        meta, _ = parse(text)
        if "!`" in text or "cli.py" in text:
            assert "Bash" in str(meta.get("allowed-tools", "")), \
                "%s runs shell but does not allow Bash" % path.name


def test_shell_substitution_has_a_fallback():
    """${CLAUDE_PLUGIN_ROOT} expansion inside a !`...` block is not something we have
    verified. Every inline command falls back to the `brain` binary on PATH, so a
    failed expansion degrades to a working command rather than a broken one."""
    for path in _files():
        text = path.read_text()
        if "!`" in text:
            assert "|| brain " in text, "%s has no fallback if the path fails" % path.name


def test_dash_does_not_block_the_command():
    """dash is a long-running server. Inline !`...` substitution would hang the command
    forever, so it must be an instruction to run in the background instead."""
    text = (COMMANDS / "dash.md").read_text()
    assert "!`" not in text
    assert "BACKGROUND" in text or "background" in text
