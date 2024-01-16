import logging

import pytest

from mkdocs_deploy import abstract, actions
from ...mock_plugin import MockTargetSession
from ...mock_wrapper import mock_wrapper


def test_delete_all_redirects_on_alias(alias: abstract.Version, mock_session: MockTargetSession):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock'}))
    mock_session.available_redirect_mechanisms['mock'].create_redirect(mock_session, alias, "1.1")

    method_1, method_calls_1 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    mock_session.redirect_mechanisms['mock'] = method_1
    mock_session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(mock_session, alias)
    assert not method_calls_2  # Only existing aliases are refreshed
    assert len(method_calls_1) == 1
    assert method_calls_1[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_1[0].kwargs["alias"] == alias

    if alias is abstract.DEFAULT_VERSION:
        assert mock_session.internal_deployment_spec.default_version is None
    else:
        assert alias not in mock_session.internal_deployment_spec.aliases


def test_delete_last_redirect_on_alias(alias: abstract.Version, mock_session: MockTargetSession):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock_2'}))
    mock_session.available_redirect_mechanisms['mock'].create_redirect(mock_session, alias, "1.1")

    method_1, method_calls_1 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    mock_session.redirect_mechanisms['mock'] = method_1
    mock_session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(mock_session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias

    if alias is abstract.DEFAULT_VERSION:
        assert mock_session.internal_deployment_spec.default_version is None
    else:
        assert alias not in mock_session.internal_deployment_spec.aliases


def test_delete_one_of_two_redirects_on_alias(alias: abstract.Version, mock_session: MockTargetSession):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'mock' ,'mock_2'}))
    mock_session.available_redirect_mechanisms['mock'].create_redirect(mock_session, alias, "1.1")

    method_1, method_calls_1 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    method_2, method_calls_2 = mock_wrapper(mock_session.redirect_mechanisms['mock'])
    mock_session.redirect_mechanisms['mock'] = method_1
    mock_session.redirect_mechanisms['mock_2'] = method_2

    actions.delete_alias(mock_session, alias, {"mock_2"})
    assert not method_calls_1  # Only named aliases are refreshed
    assert len(method_calls_2) == 1
    assert method_calls_2[0].name == 'MockRedirectMechanism.delete_redirect'
    assert method_calls_2[0].kwargs["alias"] == alias

    if alias is abstract.DEFAULT_VERSION:
        assert mock_session.internal_deployment_spec.default_version is not None
    else:
        assert alias in mock_session.internal_deployment_spec.aliases


def test_delete_missing_alias_generates_warning(
    alias: abstract.Version, caplog: pytest.LogCaptureFixture, mock_session: MockTargetSession
):
    mock_session.redirect_mechanisms['mock'], redirect_method_calls = mock_wrapper(
        mock_session.redirect_mechanisms['mock']
    )

    with caplog.at_level(logging.WARNING):
        actions.delete_alias(mock_session, alias)

    assert not redirect_method_calls
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING


def test_delete_non_existent_mechanism_raises_value_error(
    alias: abstract.Version, caplog: pytest.LogCaptureFixture, mock_session: MockTargetSession
):
    mock_session.set_alias(alias, abstract.DeploymentAlias(version_id="1.1", redirect_mechanisms={'does_not_exist'}))
    with pytest.raises(ValueError):
        actions.delete_alias(mock_session, alias, ["does_not_exist"])
