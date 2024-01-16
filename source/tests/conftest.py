import pytest

from mkdocs_deploy import abstract


@pytest.fixture(autouse=True)
def _clean_plugins(monkeypatch: pytest.MonkeyPatch):
    """Ensure that all tests run with uninitialized plugins"""
    monkeypatch.setattr(abstract, "_SOURCES", {})
    monkeypatch.setattr(abstract, "_TARGETS", {})
    monkeypatch.setattr(abstract, "_SHARED_REDIRECT_MECHANISMS", {})
