"""A worktree must be verified against ITSELF, not against the tree that owns the brain.

A git worktree under .claude/worktrees/ lives inside the main checkout, so walking up
finds the main tree's .brain/ - which is right: a project should have ONE memory,
shared across its worktrees.

But the code being committed lives in the worktree. If the gate runs the test suite in
the main checkout while you commit from a worktree, it tests the wrong code, passes, and
writes a receipt saying your changes are fine. A silent false pass.
"""

import subprocess
import sys
from pathlib import Path

from hookkit.discovery import find_brain, repo_root, work_root


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _repo_with_worktree(tmp_path):
    main = tmp_path / "project"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "src").mkdir()
    (main / "src" / "a.py").write_text("x = 1\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "init")

    brain = main / ".brain"
    (brain / "rules").mkdir(parents=True)
    (brain / "config.yml").write_text("paused: false\n")

    tree = main / ".claude" / "worktrees" / "feature"
    _git(main, "worktree", "add", "-q", str(tree), "-b", "feature")
    return main, tree


def test_the_worktree_finds_the_projects_brain(tmp_path):
    """One brain per project, shared across its worktrees. That part is correct."""
    main, tree = _repo_with_worktree(tmp_path)
    assert find_brain(tree) == main / ".brain"


def test_repo_root_still_points_at_the_brains_owner(tmp_path):
    main, tree = _repo_with_worktree(tmp_path)
    assert repo_root(main / ".brain") == main


def test_work_root_is_the_worktree_not_the_main_tree(tmp_path):
    """THE fix. Verification must run against the code you are actually committing."""
    main, tree = _repo_with_worktree(tmp_path)
    assert work_root(tree) == tree
    assert work_root(tree) != main


def test_work_root_in_a_plain_checkout_is_that_checkout(tmp_path):
    main, _ = _repo_with_worktree(tmp_path)
    assert work_root(main) == main


def test_work_root_from_a_subdirectory_finds_the_top(tmp_path):
    main, tree = _repo_with_worktree(tmp_path)
    (tree / "src").mkdir(exist_ok=True)
    assert work_root(tree / "src") == tree


def test_work_root_falls_back_to_the_brain_owner_outside_git(tmp_path):
    brain = tmp_path / "notgit" / ".brain"
    brain.mkdir(parents=True)
    assert work_root(tmp_path / "notgit", brain=brain) == tmp_path / "notgit"
