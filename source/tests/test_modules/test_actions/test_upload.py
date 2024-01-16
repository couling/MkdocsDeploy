import pytest

from mkdocs_deploy import abstract, actions, versions
from ...mock_plugin import MockSource, MockTargetSession
from ...mock_wrapper import mock_wrapper


@pytest.mark.parametrize("title", ["Version 1.1", None], ids=["Explicit Title", "Implicit Title"])
def test_upload(title: str | None, mock_source_files: dict[str, bytes]):
    VERSION = "1.1"
    source = MockSource(mock_source_files)
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


def test_upload_implicit_title_does_not_override_existing_one(mock_source_files: dict[str, bytes]):
    VERSION = "1.1"
    source = MockSource(mock_source_files)
    session, session_method_calls = mock_wrapper(MockTargetSession())
    session.start_version(VERSION, "foo bar")

    actions.upload(source=source, target=session, version_id=VERSION, title=None)

    assert session.deployment_spec.versions == {
        VERSION: versions.DeploymentVersion(title="foo bar"),
    }


def test_upload_explicit_title_overrides_existing_one(mock_source_files: dict[str, bytes]):
    VERSION = "1.1"
    VERSION_TITLE = "Version 1.1"
    source = MockSource(mock_source_files)
    session, session_method_calls = mock_wrapper(MockTargetSession())
    session.start_version(VERSION, "foo bar")

    actions.upload(source=source, target=session, version_id=VERSION, title=VERSION_TITLE)

    assert session.deployment_spec.versions == {
        VERSION: versions.DeploymentVersion(title=VERSION_TITLE),
    }


def test_upload_refreshes_aliases(mock_source_files: dict[str, bytes]):
    VERSION = "1.1"
    ALIAS = "latest"
    source = MockSource(mock_source_files)
    session = MockTargetSession()
    session.set_alias(ALIAS, abstract.DeploymentAlias(version_id=VERSION, redirect_mechanisms={'mock'}))
    method_1, method_calls_1 = mock_wrapper(session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(session.redirect_mechanisms['mock'])
    session.redirect_mechanisms['mock'] = method_1
    session.redirect_mechanisms['mock_2'] = method_2

    session.start_version(VERSION, "foo bar")

    actions.upload(source=source, target=session, version_id=VERSION, title=None)

    assert not method_calls_2
    assert len(method_calls_1) == 1
    assert method_calls_1[0].name == 'MockRedirectMechanism.refresh_redirect'
    assert method_calls_1[0].kwargs["alias"] == ALIAS
    assert method_calls_1[0].kwargs["version_id"] == VERSION
