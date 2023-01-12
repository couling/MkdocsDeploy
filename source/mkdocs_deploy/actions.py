"""
Higher level actions.

Unlike the operations sketched out in mkdocs_deploy.abstract, these operations are holistic and designed to perform
other subtasks for completion.  For example deleting a version will also delete aliases pointing to that version.  These
actions are closer to 1:1 with command line requests.  Importantly they are agnostic to the underlying Source and
TargetSession.
"""
import importlib.metadata
import logging
from typing import Iterable, Optional

from .abstract import Source, TargetSession, VersionNotFound
from .versions import DeploymentAlias

_logger = logging.getLogger(__name__)


def load_plugins() -> None:
    """
    Load all plugins.

    This should be run only ONCE at program startup.
    """
    for entry_point in importlib.metadata.entry_points(group='mkdocs_deploy.plugins'):
        try:
            _logger.debug("Enabling plugin '%s'", entry_point.name)
            enable_plugin = entry_point.load()
            enable_plugin()
        except Exception:
            _logger.error("Could not enable plugin: %s", entry_point.name, exc_info=True)
            raise



def upload(source: Source, target: TargetSession, version_id: str, title: Optional[str]) -> None:
    """
    Upload a file (to s3)
    :param source: The site to upload.  This may be a directory, or it may be zipped
    :param target: The s3 URL to upload to eg: s3://my_bucket/key_prefix
    :param version_id: The version to upload as
    :param title: The tile of this version. If None will be defaulted to either the version number or whatever the
        title was already if the version is being overwritten.
    """
    refreshing = version_id in target.deployment_spec.versions
    _logger.info("%s version %s", "refreshing" if refreshing else "Adding", version_id)
    if title is None:
        try:
            title = target.deployment_spec.versions[version_id].title
        except KeyError:
            title = version_id

    target.start_version(version_id, title)
    for filename in source.iter_files():
        with source.open_file_for_read(filename=filename) as file_obj:
            target.upload_file(
                version_id=version_id,
                filename=filename,
                file_obj=file_obj,
            )

    if refreshing:
        for alias_id in target.deployment_spec.aliases_for_version(version_id):
            refresh_alias(target, alias_id)


def delete_version(target: TargetSession, version_id: str) -> None:
    """
    Delete a version from the target
    :param target:
    :param version_id:
    """
    deployment_spec = target.deployment_spec
    for alias_id in deployment_spec.aliases_for_version(version_id):
        delete_alias(target, alias_id)
    _logger.info("Deleting version %s", version_id)
    try:
        target.delete_version(version_id)
    except VersionNotFound:
        _logger.warning("Not deleting version %s: does not exist", version_id)



def create_alias(target: TargetSession, alias_id: str, version: str,  mechanism: Optional[str] = None) -> None:
    """
    Create a new alias for a version.

    This alias must not exist as already as a version or an alias pointing to a different version.  It can exist as
    an alias for the same version with a different mechanism.  In that case it will merge the two aliases into one with
    two mechanisms.
    :param target: The target session to create the alias on
    :param alias_id: The new alias id
    :param version: The version_id to point to
    :param mechanism: The named mechanism to use.  If None then the target will choose the mechanism.
    """
    if mechanism is None:
        mechanism = "html"
    _logger.info("Creating %s alias redirect %s to %s", mechanism, alias_id, version)
    available_redirect_mechanisms = target.available_redirect_mechanisms
    existing_deployment_spec = target.deployment_spec
    if mechanism not in available_redirect_mechanisms:
        raise ValueError(f"LocalFileTreeTarget does not support redirect mechanism: {mechanism}")
    if alias_id in existing_deployment_spec.versions:
        raise ValueError(f"Cannot create an alias with the same name as an existing version. "
                         f"Delete the version first! Alias name: {alias_id}")
    if alias_id in existing_deployment_spec.aliases:
        alias = existing_deployment_spec.aliases[alias_id]
        if alias.version_id != version:
            for mechanism in alias.redirect_mechanisms:
                if mechanism not in available_redirect_mechanisms:
                    raise ValueError(f"LocalFileTreeTarget does not support redirect mechanism: {mechanism}.  "
                                     f"Unable to remove redirect for {alias_id}-->{alias.version_id}")
                available_redirect_mechanisms[mechanism].delete_redirect(target, alias_id)
            alias.version_id = version
            alias.redirect_mechanisms.clear()
        if mechanism not in alias.redirect_mechanisms:
            available_redirect_mechanisms[mechanism].create_redirect(
                session=target,
                alias=alias_id,
                version_id=version,
            )
            alias.redirect_mechanisms.add(mechanism)
            target.set_alias(alias_id, alias)
        else:
            _logger.debug("mechanism %s already in place, skipping", mechanism)
    else:
        alias = DeploymentAlias(version_id=version, redirect_mechanisms={mechanism})
        target.set_alias(alias_id, alias)
        available_redirect_mechanisms[mechanism].create_redirect(
            session=target,
            alias=alias_id,
            version_id=version,
        )


def delete_alias(target: TargetSession, alias_id: str, mechanisms: Optional[Iterable[str]] = None) -> None:
    """
    Delete an alias.

    If an iterable of mechanisms os passed, only those mechanisms will be deleted.  If that leaves no remaining
    mechanisms or no iterable is passed then the whole alias will be removed.
    :param target: The target to remove from
    :param alias_id: The alias to remove
    :param mechanisms: Optional iterable of mechanisms to remove.
    """
    _logger.info("Deleting alias %s mechanism %s", alias_id, "default" if mechanisms is None else list(mechanisms))
    try:
        alias = target.deployment_spec.aliases[alias_id]
    except KeyError:
        return
    if mechanisms is not None:
        to_delete = [mechanism for mechanism in mechanisms if mechanism in alias.redirect_mechanisms]
    else:
        to_delete = alias.redirect_mechanisms.copy()
    available_mechanisms = target.available_redirect_mechanisms
    for mechanism in to_delete:
        available_mechanisms[mechanism].delete_redirect(
            session=target,
            alias=alias_id,
        )
        alias.redirect_mechanisms.discard(mechanism)
    if alias.redirect_mechanisms:
        target.set_alias(alias_id, alias)
    else:
        target.set_alias(alias_id, None)


def refresh_alias(target: TargetSession, alias_id: str, mechanisms: Optional[Iterable[str]] = None) -> None:
    """
    Refresh redirects.

    After a version has been modified redirects may no longer work.  Refreshing an alias refreshes all the appropriate
    links to that version as it exists now.
    :param target: The target to apply changes to
    :param alias_id: The alias to refresh.
    :param mechanisms: Optional list of mechanisms to refresh.  If None (default) all will be refreshed.
    """
    _logger.info("Refreshing alias %s mechanisms %s", alias_id, "all" if mechanisms is None else list(mechanisms))
    alias = target.deployment_spec.aliases[alias_id]
    if mechanisms is not None:
        to_refresh = [mechanism for mechanism in mechanisms if mechanism in alias.redirect_mechanisms]
    else:
        to_refresh = alias.redirect_mechanisms
    available_mechanisms = target.available_redirect_mechanisms
    for mechanism in to_refresh:
        available_mechanisms[mechanism].refresh_redirect(
            session=target,
            alias=alias_id,
            version_id=alias.version_id,
        )
