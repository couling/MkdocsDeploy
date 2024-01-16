import importlib.metadata

import pytest

from mkdocs_deploy import actions
from mkdocs_deploy.plugins import aws_s3, local_filesystem, html_redirect
import functools

def test_load_plugins_calls_entry_point(monkeypatch: pytest.MonkeyPatch):
    def mock_entry_points_discovery(group: str):
        assert group == "mkdocs_deploy.plugins"
        return [mock_entry_point]

    class MockEntryPoint:
        name = "mock_entry_point"
        has_run = False

        def load(self):
            return self.run

        def run(self):
            self.has_run = True

    mock_entry_point = MockEntryPoint()
    monkeypatch.setattr(importlib.metadata, "entry_points", mock_entry_points_discovery)

    actions.load_plugins()

    assert mock_entry_point.has_run


def test_load_plugin_cascades_error(monkeypatch: pytest.MonkeyPatch):
    def mock_entry_points_discovery(group: str):
        assert group == "mkdocs_deploy.plugins"
        return [mock_entry_point]

    class MockError(Exception):
        ...

    class MockEntryPoint:
        name = "mock_entry_point"

        def load(self):
            return self.run

        def run(self):
            raise MockError()

    mock_entry_point = MockEntryPoint()
    monkeypatch.setattr(importlib.metadata, "entry_points", mock_entry_points_discovery)

    with pytest.raises(MockError):
        actions.load_plugins()


def test_inbuilt_plugins_are_loaded(monkeypatch: pytest.MonkeyPatch):
    """The aim of this is to ensure that we don't mess up entry points in pyproject.toml"""
    all_plugins = (aws_s3, local_filesystem, html_redirect)
    executed: set[str] = set()

    def enable_plugin(name: str):
        executed.add(name)

    for plugin in all_plugins:
        monkeypatch.setattr(plugin, "enable_plugin", functools.partial(enable_plugin, plugin.__name__))

    actions.load_plugins()
    assert executed == {plugin.__name__ for plugin in all_plugins}
