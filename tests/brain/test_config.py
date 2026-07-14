"""Config resolves in three layers: repo, then machine, then built-in defaults.

This is what lets the same code be safe to ship and useful to its author. A stranger
never creates ~/.brain/config.yml, so vault mirroring is off and the brain never
writes a byte outside their repo. The author sets it once and every repo mirrors
automatically. Nothing personal is hardcoded anywhere.
"""

from hookkit.config import flag, get


def _home(monkeypatch, tmp_path, **values):
    home = tmp_path / "home"
    (home / ".brain").mkdir(parents=True)
    if values:
        text = "".join("%s: %s\n" % (k, v) for k, v in values.items())
        (home / ".brain" / "config.yml").write_text(text)
    monkeypatch.setenv("HOME", str(home))
    return home


def test_repo_value_wins_over_machine_value(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, mirror="/machine/path")
    (repo / ".brain" / "config.yml").write_text("mirror: /repo/path\n")
    assert get(repo / ".brain", "mirror") == "/repo/path"


def test_machine_value_used_when_repo_has_none(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, mirror="/machine/path")
    (repo / ".brain" / "config.yml").write_text("paused: false\n")
    assert get(repo / ".brain", "mirror") == "/machine/path"


def test_default_used_when_neither_has_it(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    assert get(repo / ".brain", "mirror") is None
    assert get(repo / ".brain", "mirror", default="fallback") == "fallback"


def test_a_stranger_gets_no_mirror(repo, monkeypatch, tmp_path):
    """THE test for shippability. No machine config, no repo setting: the brain must
    never write outside the repo."""
    monkeypatch.setenv("HOME", str(tmp_path / "pristine-home"))
    assert get(repo / ".brain", "mirror") is None


def test_missing_config_files_do_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "nowhere"))
    assert get(tmp_path / "nobrain", "mirror") is None


def test_flag_reads_booleans(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    assert flag(repo / ".brain", "auto_remedy", default=False) is True


def test_flag_falls_back_to_default(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    assert flag(repo / ".brain", "nonexistent", default=True) is True


def test_machine_level_flag_applies_to_every_repo(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, auto_remedy="false")
    (repo / ".brain" / "config.yml").write_text("paused: false\n")
    assert flag(repo / ".brain", "auto_remedy", default=True) is False


def test_brain_of_none_still_reads_the_machine_config(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, mirror="/machine/path")
    assert get(None, "mirror") == "/machine/path"
