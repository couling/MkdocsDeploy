import logging
import uuid

import pytest

from mkdocs_deploy import abstract, actions, versions
from ..mock_plugin import MockSource, MockTargetSession
from ..mock_wrapper import mock_wrapper

MOCK_SOURCE_FILES = {
    "index.html": str(uuid.uuid4()).encode(),
    "subdir/foo.txt": str(uuid.uuid4()).encode(),
}


@pytest.mark.parametrize("title", ["Version 1.1", None], ids=["Explicit Title", "Implicit Title"])
def test_upload(title: str | None):
    VERSION = "1.1"
    source = MockSource(MOCK_SOURCE_FILES)
    session, session_method_calls = mock_wrapper(MockTargetSession())

    try:
        actions.upload(source=source, target=session, version_id=VERSION, title=title)

        assert session_method_calls[0].name == "MockTargetSession.start_version"

        assert session.files == {(VERSION, file): content for file, content in source.files.items()}

        assert session.deployment_spec.versions == {
            VERSION: versions.DeploymentVersion(title=title or VERSION),
        }
    except:
        session.close(success=False)
        raise
    else:
        session.close(success=True)


def test_upload_implicit_title_does_not_override_existing_one():
    VERSION = "1.1"
    source = MockSource(MOCK_SOURCE_FILES)
    session, session_method_calls = mock_wrapper(MockTargetSession())
    session.start_version(VERSION, "foo bar")

    actions.upload(source=source, target=session, version_id=VERSION, title=None)

    assert session.deployment_spec.versions == {
        VERSION: versions.DeploymentVersion(title="foo bar"),
    }


def test_upload_explicit_title_overrides_existing_one():
    VERSION = "1.1"
    VERSION_TITLE = "Version 1.1"
    source = MockSource(MOCK_SOURCE_FILES)
    session, session_method_calls = mock_wrapper(MockTargetSession())
    session.start_version(VERSION, "foo bar")

    actions.upload(source=source, target=session, version_id=VERSION, title=VERSION_TITLE)

    assert session.deployment_spec.versions == {
        VERSION: versions.DeploymentVersion(title=VERSION_TITLE),
    }


@pytest.mark.parametrize("alias", ["latest", abstract.DEFAULT_VERSION], ids=["named", "default"])
def test_refresh_all_redirects_on_alias(alias: abstract.Version):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    session.available_redirect_mechanisms['mock'].create_redirect(session, abstract.DEFAULT_VERSION, "1.1")
    session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock'}))

    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    actions.refresh_alias(session, alias)
    assert not method_calls_2  # Only existing aliases are refreshed
    assert len(method_calls_1) == 1
    assert method_calls_1[0].name == 'MockRedirectMechanism.refresh_redirect'
    assert method_calls_1[0].kwargs["alias"] == alias
    assert method_calls_1[0].kwargs["version_id"] == "1.1"


@pytest.mark.parametrize("alias", ["latest", abstract.DEFAULT_VERSION], ids=["Named", "Default"])
def test_refresh_specific_redirect_on_alias(alias: abstract.Version):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock_2'}))
    session.available_redirect_mechanisms['mock'].create_redirect(session, abstract.DEFAULT_VERSION, "1.1")

    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    actions.refresh_alias(session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.refresh_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias
    assert method_calls_2[0].kwargs["version_id"] == "1.1"



@pytest.mark.parametrize("alias", ["latest", abstract.DEFAULT_VERSION], ids=["named", "default"])
def test_delete_all_redirects_on_alias(alias: abstract.Version):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    session.available_redirect_mechanisms['mock'].create_redirect(session, abstract.DEFAULT_VERSION, "1.1")
    session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock'}))

    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(session, alias)
    assert not method_calls_2  # Only existing aliases are refreshed
    assert len(method_calls_1) == 1
    assert method_calls_1[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_1[0].kwargs["alias"] == alias

    assert alias not in session.aliases


def test_refresh_missing_alias_logs_warning(caplog: pytest.LogCaptureFixture):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)

    session.redirect_mechanisms['mock'], method_calls = mock_wrapper(session.redirect_mechanisms['mock'])
    with caplog.at_level(level=logging.WARNING):
        actions.refresh_alias(session, "not_an_alias", {"mock"})

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert not method_calls


@pytest.mark.parametrize("alias", ["latest", abstract.DEFAULT_VERSION], ids=["Named", "Default"])
def test_delete_last_redirect_on_alias(alias: abstract.Version):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock_2'}))
    session.available_redirect_mechanisms['mock'].create_redirect(session, abstract.DEFAULT_VERSION, "1.1")

    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias

    assert alias not in session.aliases


@pytest.mark.parametrize("alias", ["latest", abstract.DEFAULT_VERSION], ids=["Named", "Default"])
def test_delete_one_of_two_redirects_on_alias(alias: abstract.Version):
    session = MockTargetSession()
    for version in ("1.0", "1.1", "2.0"):
        session.start_version(version, version)
    session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock' ,'mock_2'}))
    session.available_redirect_mechanisms['mock'].create_redirect(session, abstract.DEFAULT_VERSION, "1.1")

    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias

    assert alias in session.aliases
