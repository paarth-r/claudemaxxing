import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "brain"
sys.path.insert(0, str(PLUGIN))


@pytest.fixture
def repo(tmp_path):
    """A fake project with a .brain/ directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    brain = tmp_path / ".brain"
    (brain / "rules").mkdir(parents=True)
    (brain / "_receipts").mkdir(parents=True)
    (brain / "config.yml").write_text("paused: false\nauto_remedy: true\n")
    return tmp_path


@pytest.fixture
def bare_repo(tmp_path):
    """A project with NO .brain/ directory. The zero-footprint case."""
    (tmp_path / "src").mkdir()
    return tmp_path
