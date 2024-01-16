import logging

import pytest

from mkdocs_deploy import abstract, actions
from ...mock_plugin import MockTargetSession
from ...mock_wrapper import mock_wrapper


def test_refresh_all_redirects_on_alias(alias: abstract.Version, mock_session: MockTargetSession):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock'}))
    mock_session.available_redirect_mechanisms['mock'].create_redirect(mock_session, alias, "1.1")

    method_1, method_calls_1 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    mock_session.redirect_mechanisms['mock'] = method_1
    mock_session.redirect_mechanisms['mock_2'] = method_2

    actions.refresh_alias(mock_session, alias)
    assert not method_calls_2  # Only existing aliases are refreshed
    assert len(method_calls_1) == 1
    assert method_calls_1[0].name == 'MockRedirectMechanism.refresh_redirect'
    assert method_calls_1[0].kwargs["alias"] == alias
    assert method_calls_1[0].kwargs["version_id"] == "1.1"


def test_refresh_specific_redirect_on_alias(alias: abstract.Version, mock_session: MockTargetSession):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock_2'}))
    mock_session.available_redirect_mechanisms['mock'].create_redirect(mock_session, alias, "1.1")

    method_1, method_calls_1 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    mock_session.redirect_mechanisms['mock'] = method_1
    mock_session.redirect_mechanisms['mock_2'] = method_2

    actions.refresh_alias(mock_session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.refresh_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias
    assert method_calls_2[0].kwargs["version_id"] == "1.1"


def test_refresh_missing_alias_logs_warning(caplog: pytest.LogCaptureFixture, mock_session: MockTargetSession):
    mock_session.redirect_mechanisms['mock'], method_calls = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    with caplog.at_level(level=logging.WARNING):
        actions.refresh_alias(mock_session, "not_an_alias", {"mock"})

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert not method_calls
