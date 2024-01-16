import pytest
import logging
from mkdocs_deploy import abstract
from mkdocs_deploy.actions import create_alias, delete_version
from ...mock_plugin import MockTargetSession
from ...mock_wrapper import mock_wrapper, MethodCall


def test_delete_version_with_aliases(mock_session: MockTargetSession, alias: abstract.Version):
    mock_session.redirect_mechanisms["mock"], mechanism_calls = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    create_alias(mock_session, alias, "1.1")

    mock_session, session_calls = mock_wrapper(mock_session)

    delete_version(mock_session, "1.1")

    assert "1.1" not in mock_session.internal_deployment_spec.versions
    if alias is abstract.DEFAULT_VERSION:
        assert mock_session.internal_deployment_spec.default_version is None
    else:
        assert alias not in mock_session.internal_deployment_spec.aliases

    assert MethodCall("MockTargetSession.set_alias", (alias, None), {}) in session_calls


def test_delete_missing_version(mock_session: MockTargetSession, alias: abstract.Version, caplog: pytest.LogCaptureFixture):
    mock_session.redirect_mechanisms["mock"], mechanism_calls = mock_wrapper(mock_session.redirect_mechanisms["mock"])

    mock_session, session_calls = mock_wrapper(mock_session)

    with caplog.at_level(logging.WARNING):
        delete_version(mock_session, "foo")

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING

