import uuid

import pytest

from mkdocs_deploy import abstract
from .mock_plugin import MockTargetSession


@pytest.fixture(autouse=True)
def _clean_plugins(monkeypatch: pytest.MonkeyPatch):
    """Ensure that all tests run with uninitialized plugins"""
    monkeypatch.setattr(abstract, "_SOURCES", {})
    monkeypatch.setattr(abstract, "_TARGETS", {})
    monkeypatch.setattr(abstract, "_SHARED_REDIRECT_MECHANISMS", {})


@pytest.fixture()
def mock_source_files() -> dict[str, bytes]:
    return {
        "index.html": str(uuid.uuid4()).encode(),
        "subdir/foo.txt": str(uuid.uuid4()).encode(),
    }


@pytest.fixture()
def mock_session() -> MockTargetSession:
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    return session


@pytest.fixture(params=["latest", abstract.DEFAULT_VERSION], ids=["Named_alias", "Default_alias"])
def alias(request) -> abstract.Version:
    return request.param
