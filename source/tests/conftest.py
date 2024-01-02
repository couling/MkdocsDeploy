from pathlib import Path

import pytest

from mkdocs_deploy import abstract
from mkdocs_deploy.plugins import local_filesystem


@pytest.fixture(autouse=True)
def _clean_plugins(monkeypatch: pytest.MonkeyPatch):
    """Ensure that all tests run with uninitialized plugins"""
    monkeypatch.setattr(abstract, "_SOURCES", {})
    monkeypatch.setattr(abstract, "_TARGETS", {})

@pytest.fixture()
def mock_source_path(tmp_path: Path) -> Path:
    base_path = tmp_path / "mock_source"
    base_path.mkdir(exist_ok=False, parents=True)
    return base_path


@pytest.fixture()
def mock_source(mock_source_path: Path) -> abstract.Source:
    return local_filesystem.LocalFileTreeSource(mock_source_path)


@pytest.fixture()
def mock_target_path(tmp_path: Path) -> Path:
    base_path = tmp_path / "mock_target"
    base_path.mkdir(exist_ok=False, parents=True)
    return base_path


@pytest.fixture()
def mock_target(mock_target_path: Path) -> abstract.Target:
    return local_filesystem.LocalFileTreeTarget(str(mock_target_path))
