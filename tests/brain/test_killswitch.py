from hookkit.killswitch import config_flag, is_disabled


def test_not_disabled_by_default(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert is_disabled(repo / ".brain") is False


def test_disabled_when_repo_is_paused(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (repo / ".brain" / "config.yml").write_text("paused: true\n")
    assert is_disabled(repo / ".brain") is True


def test_disabled_by_global_flag_file(repo, monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".brain").mkdir(parents=True)
    (home / ".brain" / "DISABLED").write_text("")
    monkeypatch.setenv("HOME", str(home))
    assert is_disabled(repo / ".brain") is True


def test_global_flag_wins_even_when_brain_is_none(monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".brain").mkdir(parents=True)
    (home / ".brain" / "DISABLED").write_text("")
    monkeypatch.setenv("HOME", str(home))
    assert is_disabled(None) is True


def test_missing_config_is_not_disabled(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (repo / ".brain" / "config.yml").unlink()
    assert is_disabled(repo / ".brain") is False


def test_config_flag_reads_value(repo):
    assert config_flag(repo / ".brain", "auto_remedy", default=False) is True


def test_config_flag_default_when_absent(repo):
    assert config_flag(repo / ".brain", "nonexistent", default=True) is True
