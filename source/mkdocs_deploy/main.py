import logging
from contextlib import ExitStack
from typing import Optional

import click
import sys

from . import actions
from .abstract import source_for_url, target_for_url

_logger =logging.getLogger(__name__)


_LOG_FORMAT = "%(levelname)s: %(message)s"
_DEBUG_FORMAT = "%(levelname)s: %(name)s:  %(message)s"
_REDIRECT_TYPE = click.option(
    "--redirect-type",
    "-m",
    help="The alias redirect type.  Default 'html' generating html files which themselves redirect to others."
)
_LOG_LEVEL_NAMES = [name for name, val in logging._nameToLevel.items() if val]


@click.group()
@click.option("--log-level", help=f"Set log level. Valid values are {', '.join(_LOG_LEVEL_NAMES)}", default="INFO")
def main(log_level: str):
    """
    Version aware Mkdocs deployment tool.
    """
    numeric_level = logging.getLevelName(log_level)
    if not isinstance(numeric_level, int):
        raise click.ClickException(f"Unknown log level {log_level}")
    logging.basicConfig(
        stream=sys.stderr,
        level=numeric_level,
        format=_LOG_FORMAT if numeric_level >= logging.INFO else _DEBUG_FORMAT,
    )
    actions.load_plugins()


@main.command()
@click.argument("TARGET_URL")
@click.argument("SITE")
@click.argument("VERSION")
@click.option("--alias", "-a", multiple=True, help="Alias for this version")
@click.option("--title", "-t", help="A title for this version")
@_REDIRECT_TYPE
def deploy(
    site: str, version: str, target_url: str, title:Optional[str], alias: tuple[str], redirect_type: tuple[str, ...]
):
    """
    Deploy a version of your documentation

    SITE: The built site to publish. This will have been created with mkdocs build
    This built site may optionally be zipped or a tar file

    VERSION: The version number to deploy as.

    TARGET_URL: Where the site is to be published excluding the version number
    """
    target = target_for_url(target_url=target_url)
    with ExitStack() as exit_stack:
        try:
            source = exit_stack.enter_context(source_for_url(source_url=site))
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc))
        target_session = exit_stack.enter_context(target.start_session())
        actions.upload(source=source, target=target_session, version_id=version, title=title)
        for _alias in alias:
            actions.create_alias(
                target=target_session,
                alias_id=_alias,
                version=version,
                mechanisms=redirect_type or None,
            )


@main.command()
@click.argument("TARGET_URL")
@click.argument("VERSION")
def delete_version(version: str, target_url: str):
    """
    Delete a version of your documentation and all aliases pointing to it.

    VERSION: The version number to deploy as.
    TARGET_URL: Where the site is to be published excluding the version number
    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        actions.delete_version(target_session, version)


@main.command()
@click.argument("TARGET_URL")
@click.argument("VERSION")
@click.argument("ALIAS")
@_REDIRECT_TYPE
def set_alias(target_url: str, version: str, alias, redirect_type: tuple[str, ...]):
    """
    Set an alias for a specific version, or add a redirect type for that alias.
    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        actions.create_alias(target=target_session, alias_id=alias, version=version, mechanisms=redirect_type or None)


@main.command()
@click.argument("TARGET_URL")
@click.argument("ALIAS", required=False)
@click.option(
    "--all-aliases",
    is_flag=True,
    help="Delete all redirects for aliases of a specific alias types. "
         "--alias-type must be specified at least once and ALIAS must not be given as an argument."
)
@click.option("--redirect-type", "-m", help="The alias redirect mechanism.")
def delete_alias(alias: Optional[str], target_url: str, redirect_type: tuple[str, ...], all_aliases: bool):
    """
    Delete an alias or single redirection type.

    If ALIAS is set and not --redirect-type then the alias will be completely deleted and all redirects for it removed.

    If both ALIAS and --redirect-type are set then just one redirect will be removed of a single type.  The alias
    meta references to the alias will only be removed if it leaves no remaining redirects.

    --all-aliases Exists for preparation of site moves.
    --
    """
    target = target_for_url(target_url=target_url)
    if all_aliases:
        if alias is not None:
            raise click.ClickException("Cannot specify an ALIAS and --all-aliases")
        if not redirect_type:
            raise click.ClickException("Must specify --redirect-type if --all-aliases is set")
        with target.start_session() as target_session:
            for alias_id, alias in target_session.deployment_spec.aliases.items():
                matching_mechanisms = [_type for _type in redirect_type if _type in alias.redirect_mechanisms]
                if matching_mechanisms:
                    actions.delete_alias(target=target_session, alias_id=alias_id, mechanisms=matching_mechanisms)
    if alias is not None:
        with target.start_session() as target_session:
            actions.delete_alias(target=target_session, alias_id=alias, mechanisms=redirect_type or None)
    else:
        raise click.ClickException("If ALIAS is not given both --all-aliases and --alias-type must be set")


@main.command()
@click.argument("TARGET_URL")
@click.argument("VERSION")
@_REDIRECT_TYPE
def set_default(target_url: str, version: str, redirect_type: tuple[str, ...]):
    """
    Set the default version or alias for your site.

    This is very similar to an alias and makes use of redirect rules.
    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        actions.create_alias(target_session, ..., version, redirect_type or None)


@main.command()
@click.argument("TARGET_URL")
@_REDIRECT_TYPE
def clear_default(target_url: str, redirect_type: tuple[str, ...]):
    """
    Clear the default version or alias setting
    for your site.

    This is very similar to an alias and makes use of redirect rules.
    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        actions.delete_alias(target_session, ..., redirect_type or None)


@main.command()
@click.argument("TARGET_URL")
@click.option("--json", is_flag=True, help="Format as json")
def describe(target_url: str, json: bool):
    """
    Describe the current deployment setup of your software versions

    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        if json:
            print(target_session.deployment_spec.json(sort_keys=True, indent=True))
        else:
            deployment_spec = target_session.deployment_spec
            if deployment_spec.default_version is None:
                print("⛔️ No default version")
            else:
                print(f"👋 Default version → {deployment_spec.default_version.version_id} "
                      f"['{', '.join(deployment_spec.default_version.redirect_mechanisms)}']")
            for version_id, version in deployment_spec.versions.items():
                print(f"📦 {version_id} - '{version.title}'")
            for alias_id, alias in deployment_spec.aliases.items():
                print(f"🔗 {alias_id} → {version_id} ['{', '.join(alias.redirect_mechanisms)}']")
