import uuid
from pathlib import Path

import pytest

from mkdocs_deploy import abstract, actions, versions
from ..mock_wrapper import mock_wrapper


@pytest.fixture()
def mock_source_files(mock_source: abstract.Source, mock_source_path: Path) -> dict[str, bytes]:
    (mock_source_path / "index.html").write_text(str(uuid.uuid4()))
    (mock_source_path / "subdir").mkdir(exist_ok=False)
    (mock_source_path / "subdir" / "foo.txt").write_text(str(uuid.uuid4()))
    results = {}
    for file in mock_source.iter_files():
        with mock_source.open_file_for_read(file) as file_handle:
            results[file] = file_handle.read()
    return results


@pytest.mark.parametrize("title", ["Version 1.1", None], ids=["Explicit Title", "Implicit Title"])
def test_upload(
    mock_source: abstract.Source, mock_target: abstract.Target, mock_source_files: dict[str, bytes], title: str | None
):
    VERSION = "1.1"
    session, session_method_calls = mock_wrapper(mock_target.start_session())
    try:
        actions.upload(
            source=mock_source,
            target=session,
            version_id=VERSION,
            title=title,
        )

        assert session_method_calls[0].name == "start_version"

        uploaded_files = set(session.iter_files(VERSION))
        assert uploaded_files == set(mock_source_files.keys())
        for file in mock_source_files.keys():
            with session.download_file(VERSION, file) as file_handle:
                assert file_handle.read() == mock_source_files[file]


        assert session.deployment_spec.versions == {
            VERSION: versions.DeploymentVersion(title=title or VERSION),
        }
    except:
        session.close(success=False)
        raise
    else:
        session.close(success=True)


def test_upload_implicit_title_does_not_override_existing_one(
    mock_source: abstract.Source, mock_target: abstract.Target, mock_source_files: dict[str, bytes]
):
    VERSION = "1.1"
    session = mock_target.start_session()
    try:
        session._deployment_spec.versions[VERSION] = versions.DeploymentVersion(title="foo bar") # type: ignore
        actions.upload(
            source=mock_source,
            target=session,
            version_id=VERSION,
            title=None,
        )

        uploaded_files = set(session.iter_files(VERSION))
        assert uploaded_files == set(mock_source_files.keys())
        for file in mock_source_files.keys():
            with session.download_file(VERSION, file) as file_handle:
                assert file_handle.read() == mock_source_files[file]


        assert session.deployment_spec.versions == {
            VERSION: versions.DeploymentVersion(title="foo bar" or VERSION),
        }
    except:
        session.close(success=False)
        raise
    else:
        session.close(success=True)


def test_upload_explicit_title_overrides_existing_one(
    mock_source: abstract.Source, mock_target: abstract.Target, mock_source_files: dict[str, bytes]
):
    VERSION = "1.1"
    VERSION_TITLE = "Version 1.1"
    session = mock_target.start_session()
    try:
        session._deployment_spec.versions[VERSION] = versions.DeploymentVersion(title="foo bar") # type: ignore
        actions.upload(
            source=mock_source,
            target=session,
            version_id=VERSION,
            title=VERSION_TITLE,
        )

        uploaded_files = set(session.iter_files(VERSION))
        assert uploaded_files == set(mock_source_files.keys())
        for file in mock_source_files.keys():
            with session.download_file(VERSION, file) as file_handle:
                assert file_handle.read() == mock_source_files[file]


        assert session.deployment_spec.versions == {
            VERSION: versions.DeploymentVersion(title=VERSION_TITLE or VERSION),
        }
    except:
        session.close(success=False)
        raise
    else:
        session.close(success=True)