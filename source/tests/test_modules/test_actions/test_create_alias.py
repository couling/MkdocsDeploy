from typing import Collection

import pytest

from mkdocs_deploy import abstract
from mkdocs_deploy.actions import create_alias
from ...mock_plugin import MockTargetSession
from ...mock_wrapper import mock_wrapper


@pytest.mark.parametrize("mechanisms", [("mock",), None], ids=["explicit_mechanism", "implicit_mechanism"])
def test_create_new_alias(mock_session: MockTargetSession, alias: abstract.Version, mechanisms: Collection[str] | None):
    mock_session.redirect_mechanisms["mock"], mechanism_calls = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mock_session, session_calls = mock_wrapper(mock_session)
    create_alias(mock_session, alias, "1.1", mechanisms)
    assert session_calls[-1].name == "MockTargetSession.set_alias"
    assert len(mechanism_calls) == 1
    assert mechanism_calls[0].name == "MockRedirectMechanism.create_redirect"


def test_add_mechanism(mock_session: MockTargetSession, alias: abstract.Version):
    create_alias(mock_session, alias, "1.1", ["mock"])
    mechanism_1, calls_1 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mechanism_2, calls_2 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mock_session.redirect_mechanisms["mock"] = mechanism_1
    mock_session.redirect_mechanisms["mock_2"] = mechanism_2
    create_alias(mock_session, alias, "1.1", ["mock", "mock_2"])
    assert not calls_1
    assert len(calls_2) == 1
    assert calls_2[0].name == "MockRedirectMechanism.create_redirect"


def test_change_version_change_mechanism(mock_session: MockTargetSession, alias: abstract.Version):
    create_alias(mock_session, alias, "1.1", ["mock"])

    # Notice that mock_2 is added AFTER the version is created.
    # The intended behaviour here is to create all available mechanisms
    mechanism_1, calls_1 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mechanism_2, calls_2 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mock_session.redirect_mechanisms["mock"] = mechanism_1
    mock_session.redirect_mechanisms["mock_2"] = mechanism_2
    create_alias(mock_session, alias, "2.0", ["mock_2"])

    assert len(calls_1) == 1
    assert calls_1[0].name == "MockRedirectMechanism.delete_redirect"
    assert len(calls_2) == 1
    assert calls_2[0].name == "MockRedirectMechanism.create_redirect"


def test_change_version_only(mock_session: MockTargetSession, alias: abstract.Version):
    create_alias(mock_session, alias, "1.1", ["mock"])

    # Notice that mock_2 is added AFTER the version is created.
    # The intended behaviour here is to create all available mechanisms
    mechanism_1, calls_1 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mechanism_2, calls_2 = mock_wrapper(mock_session.redirect_mechanisms["mock"])
    mock_session.redirect_mechanisms["mock"] = mechanism_1
    mock_session.redirect_mechanisms["mock_2"] = mechanism_2
    create_alias(mock_session, alias, "2.0", ["mock"])

    assert len(calls_1) == 1
    assert calls_1[0].name == "MockRedirectMechanism.refresh_redirect"
    assert not calls_2


def test_clobbering_version_with_alias_fails(mock_session: MockTargetSession):
    with pytest.raises(ValueError):
        create_alias(mock_session, "2.0", "1.1")


def test_creating_non_existent_mechanism_fails(mock_session: MockTargetSession):
    with pytest.raises(ValueError):
        create_alias(mock_session, "2.0", "1.1", ["foo"])


def test_deleting_non_existent_mechanism_fails(mock_session: MockTargetSession, alias: abstract.Version):
    """If a code change means configuration has redirects that cannot now be deleted, we should error"""
    mock_session.redirect_mechanisms["phantom"] = mock_session.redirect_mechanisms["mock"]
    create_alias(mock_session, alias, "2.0", ["mock", "phantom"])
    del mock_session.redirect_mechanisms["phantom"]

    with pytest.raises(ValueError):
        create_alias(mock_session, alias, "2.0", ["mock"])
