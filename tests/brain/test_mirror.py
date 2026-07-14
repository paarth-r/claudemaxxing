from hookkit.mirror import export, target


def _home(monkeypatch, tmp_path, mirror=None):
    home = tmp_path / "home"
    (home / ".brain").mkdir(parents=True)
    if mirror:
        (home / ".brain" / "config.yml").write_text("mirror: %s\n" % mirror)
    monkeypatch.setenv("HOME", str(home))
    return home


def _populate(repo):
    (repo / ".brain" / "rules" / "r.md").write_text("---\nid: r\n---\n\n# R\n")
    gotchas = repo / ".brain" / "gotchas"
    gotchas.mkdir(parents=True, exist_ok=True)
    (gotchas / "g.md").write_text("# G\n")
    (repo / ".brain" / "index.md").write_text("## Project brain\n")
    (repo / ".brain" / "_receipts" / "s.jsonl").write_text('{"cmd": "secret"}\n')
    queue = repo / ".brain" / "_queue"
    queue.mkdir(parents=True, exist_ok=True)
    (queue / "corrections.jsonl").write_text('{"prompt": "private"}\n')


def test_no_target_when_nothing_is_configured(repo, monkeypatch, tmp_path):
    """A stranger installing this must never write outside their repo."""
    monkeypatch.setenv("HOME", str(tmp_path / "pristine"))
    assert target(repo / ".brain") is None


def test_machine_config_alone_sets_the_target(repo, monkeypatch, tmp_path):
    """The author case: set it once, every repo mirrors, no per-repo setup."""
    vault = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault))
    assert target(repo / ".brain") == vault


def test_repo_config_overrides_the_machine(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, mirror=str(tmp_path / "machine"))
    (repo / ".brain" / "config.yml").write_text("mirror: %s\n" % (tmp_path / "repo"))
    assert target(repo / ".brain") == tmp_path / "repo"


def test_tilde_is_expanded(repo, monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path, mirror="~/vault")
    assert target(repo / ".brain") == home / "vault"


def test_export_does_nothing_without_a_target(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "pristine"))
    _populate(repo)
    assert export(repo / ".brain", "myrepo") == 0


def test_export_copies_rules_and_notes(repo, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault))
    _populate(repo)

    count = export(repo / ".brain", "myrepo")
    assert count >= 3
    assert (vault / "myrepo" / "rules" / "r.md").exists()
    assert (vault / "myrepo" / "gotchas" / "g.md").exists()
    assert (vault / "myrepo" / "index.md").exists()


def test_export_never_copies_private_machinery(repo, monkeypatch, tmp_path):
    """Receipts hold command lines and the queue holds raw prompts. Neither belongs
    in a synced vault."""
    vault = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault))
    _populate(repo)

    export(repo / ".brain", "myrepo")
    assert not (vault / "myrepo" / "_receipts").exists()
    assert not (vault / "myrepo" / "_queue").exists()
    assert "secret" not in _all_text(vault)
    assert "private" not in _all_text(vault)


def test_export_is_idempotent(repo, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault))
    _populate(repo)

    first = export(repo / ".brain", "myrepo")
    second = export(repo / ".brain", "myrepo")
    assert first == second


def test_export_reflects_deletions(repo, monkeypatch, tmp_path):
    """An archived rule must disappear from the vault, not linger as a ghost."""
    vault = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault))
    _populate(repo)
    export(repo / ".brain", "myrepo")

    (repo / ".brain" / "rules" / "r.md").unlink()
    export(repo / ".brain", "myrepo")
    assert not (vault / "myrepo" / "rules" / "r.md").exists()


def test_export_to_an_unwritable_target_is_silent(repo, monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path, mirror="/proc/nope/cannot-write-here")
    _populate(repo)
    assert export(repo / ".brain", "myrepo") == 0  # must not raise


def _all_text(root):
    parts = []
    for path in root.rglob("*"):
        if path.is_file():
            try:
                parts.append(path.read_text())
            except OSError:
                pass
    return "\n".join(parts)


def test_the_exported_brain_is_an_obsidian_vault(repo, monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault_dir))
    _populate(repo)
    export(repo / ".brain", "myrepo")
    assert (vault_dir / "myrepo" / ".obsidian" / "app.json").is_file()


def test_export_never_destroys_obsidian_settings(repo, monkeypatch, tmp_path):
    """Obsidian keeps graph layout, hotkeys, and appearance in .obsidian/ inside the
    vault. Wiping it on every session-end would vandalise the user's own settings."""
    vault_dir = tmp_path / "vault"
    _home(monkeypatch, tmp_path, mirror=str(vault_dir))
    _populate(repo)
    export(repo / ".brain", "myrepo")

    settings = vault_dir / "myrepo" / ".obsidian" / "workspace.json"
    settings.write_text('{"my": "carefully arranged graph layout"}')

    export(repo / ".brain", "myrepo")  # a second session ends

    assert settings.is_file(), "the user's vault settings must survive a re-export"
    assert "carefully arranged" in settings.read_text()
