from pathlib import Path

from hookkit.discovery import find_brain, repo_root


def test_finds_brain_in_repo_root(repo):
    assert find_brain(repo) == repo / ".brain"


def test_finds_brain_from_nested_subdirectory(repo):
    nested = repo / "src"
    assert find_brain(nested) == repo / ".brain"


def test_returns_none_without_brain(bare_repo):
    assert find_brain(bare_repo) is None


def test_returns_none_from_nested_dir_without_brain(bare_repo):
    assert find_brain(bare_repo / "src") is None


def test_repo_root_is_parent_of_brain(repo):
    assert repo_root(repo / ".brain") == repo


def test_missing_start_dir_returns_none():
    assert find_brain(Path("/definitely/not/a/real/path/anywhere")) is None
