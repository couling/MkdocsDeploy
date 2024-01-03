import uuid

import pytest

from mkdocs_deploy import actions, versions
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

        assert session_method_calls[0].name == "start_version"

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