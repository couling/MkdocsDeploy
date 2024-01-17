import io
import uuid

import pytest

from mkdocs_deploy import abstract
from mkdocs_deploy.plugins import html_redirect
from mkdocs_deploy.shared_implementations import relative_link
from ..mock_plugin import MockTargetSession


@pytest.fixture()
def mock_session(mock_session: MockTargetSession, mock_source_files: dict[str, bytes]):
    for version in mock_session.internal_deployment_spec.versions:
        for filename, data in mock_source_files.items():
            mock_session.upload_file(version, filename, io.BytesIO(data))
    return mock_session


@pytest.fixture()
def mock_source_files() -> dict[str, bytes]:
    return {
        "index.html": str(uuid.uuid4()).encode(),
        "subdir/foo.html": str(uuid.uuid4()).encode(),
        "subdir/foo.txt": str(uuid.uuid4()).encode(),
        "difficult file &?$ name.html": str(uuid.uuid4()).encode(),
    }


def test_enable_plugin():
    assert "html" not in abstract._SHARED_REDIRECT_MECHANISMS
    html_redirect.enable_plugin()
    assert isinstance(abstract._SHARED_REDIRECT_MECHANISMS["html"], html_redirect.HtmlRedirect)


def test_create_alias(mock_session: MockTargetSession, mock_source_files: dict[str, bytes]):
    mock_session.set_alias("latest", abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms=set()))

    redirect = html_redirect.HtmlRedirect()
    redirect.create_redirect(
        session=mock_session,
        alias="latest",
        version_id="1.1",
    )

    uploaded_files = {
        file_name: content
        for (version, file_name), content in mock_session.files.items()
        if version == "latest"
    }
    # Check there is a redirect file for every htm and html file
    assert set(uploaded_files) == {
        file_name
        for file_name in mock_source_files
        if file_name.endswith(".htm") or file_name.endswith(".html")
    }
    # These are redirects not copies
    for file_name, content in uploaded_files.items():
        link_url = relative_link("1.1",file_name)
        assert f'"{link_url}"'.encode("utf8") in content


def test_creating_alias_deletes_files(mock_session: MockTargetSession, mock_source_files: dict[str, bytes]):
    mock_session.set_alias("latest", abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms=set()))
    mock_session.files[("latest", "index.html")] = b'' # This should get overwritten
    mock_session.files[("latest", "what_is_this/index.html")] = b'' # This should get deleted
    assert "what_is_this/index.html" not in mock_source_files  # Sanity check

    redirect = html_redirect.HtmlRedirect()
    redirect.create_redirect(
        session=mock_session,
        alias="latest",
        version_id="1.1",
    )

    # Check this file was overwritten
    assert f'"{relative_link("1.1", "index.html")}"'.encode("utf8") in mock_session.files[("latest", "index.html")]

    # Check this file was deleted
    assert ("latest", "what_is_this/index.html") not in mock_session.files


def test_create_default_version_redirect(mock_session: MockTargetSession):
    redirect = html_redirect.HtmlRedirect()
    redirect.create_redirect(
        session=mock_session,
        alias=abstract.DEFAULT_VERSION,
        version_id="1.1",
    )

    uploaded_files = {
        file_name: content
        for (version, file_name), content in mock_session.files.items()
        if version is abstract.DEFAULT_VERSION
    }
    # Check there is a redirect file for every htm and html file
    assert set(uploaded_files) == {"index.html"}

    link_url = relative_link("1.1", "", from_root=True)
    assert f'"{link_url}"'.encode("utf8") in uploaded_files["index.html"]


def test_refreshing_alias_deletes_files(mock_session: MockTargetSession, mock_source_files: dict[str, bytes]):
    mock_session.set_alias("latest", abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms=set()))
    mock_session.files[("latest", "index.html")] = b'' # This should get overwritten
    mock_session.files[("latest", "what_is_this/index.html")] = b'' # This should get deleted
    assert "what_is_this/index.html" not in mock_source_files  # Sanity check

    redirect = html_redirect.HtmlRedirect()
    redirect.refresh_redirect(
        session=mock_session,
        alias="latest",
        version_id="1.1",
    )

    # Check this file was overwritten
    assert f'"{relative_link("1.1", "index.html")}"'.encode("utf8") in mock_session.files[("latest", "index.html")]

    # Check this file was deleted
    assert ("latest", "what_is_this/index.html") not in mock_session.files


def test_delete_default_version(mock_session: MockTargetSession):
    mock_session.files[(abstract.DEFAULT_VERSION, "index.html")] = b''
    mock_session.files[(abstract.DEFAULT_VERSION, "foo_bar.html")] = b'leave me alone'

    redirect = html_redirect.HtmlRedirect()
    redirect.delete_redirect(mock_session, abstract.DEFAULT_VERSION)

    assert (abstract.DEFAULT_VERSION, "index.html") not in mock_session.files
    assert mock_session.files[(abstract.DEFAULT_VERSION, "foo_bar.html")] == b'leave me alone'


def test_delete_named_version(mock_session: MockTargetSession):
    mock_session.set_alias("latest", abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms=set()))
    mock_session.files[("latest", "index.html")] = b'delete me'
    mock_session.files[("latest", "foo_bar.jpg")] = b'delete me'
    mock_session.files[("latest", "sub_dir/foo_bar.html")] = b'delete me'

    redirect = html_redirect.HtmlRedirect()
    redirect.delete_redirect(mock_session, "latest")

    assert not any(True for version, file_name in mock_session.files if version == "latest")
