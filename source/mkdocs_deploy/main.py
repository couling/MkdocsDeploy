import click
import logging
import pydantic.json
import sys
import yaml
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

from . import actions
from .abstract import source_for_url, target_for_url
from .configuration import MkdocsDeployConfig, find_configuration, load_configuration

_logger =logging.getLogger(__name__)

# https://github.com/python/cpython/blob/7b21108445969398f6d1db9234fc0fe727565d2e/Lib/json/encoder.py#L78
JSONABLE_TYPES = (dict, list, tuple, str, int, float, bool, type(None))


_LOG_FORMAT = "%(levelname)s: %(message)s"
_DEBUG_FORMAT = "%(levelname)s: %(name)s:  %(message)s"
_LOG_LEVEL_NAMES = [name for name, val in logging._nameToLevel.items() if val]


@click.group()
@click.option(
    "--config-file",
    help="Configuration file. If not specified, one will be searched for starting in CWD and working up",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.option("--log-level", help=f"Set log level. Valid values are {', '.join(_LOG_LEVEL_NAMES)}", default="INFO")
@click.option("--built-site", help="URL or file path to the built site - output from mkdocs")
@click.option("--built-site-pattern", help="Glob pattern for a file path to the built site. Replaces --built-site-url")
@click.option("--deploy-url", help="URL to deploy to")
@click.option("--redirect-mechanisms", help="Coma seperated list of alias mechanisms. Defaults to just 'html'")
def main(log_level: str, config_file: Optional[Path], **overrides):
    """
    Version aware Mkdocs deployment tool.

    Options can override configuration files.  Configuration can be found in any of "mkdocs-deploy.json",
    "mkdocs-deploy.yaml, or pyproject.toml".
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
    if config_file is not None:
        config = click.get_current_context().obj = load_configuration(config_path=config_file)
    else:
        config = click.get_current_context().obj = find_configuration()
    for name, value in overrides.items():
        if value is not None:
            if name == "redirect_mechanisms":
                value = value.split(",")
            setattr(config, name, value)
    if config.deploy_url is None:
        raise click.ClickException("No deployment URL set")


@main.command()
@click.argument("VERSION")
@click.argument("TITLE", required=False)
@click.option("--alias", "-a", multiple=True, help="Additional alias for this version")
@click.option("--no-default-alias", is_flag=True, help="Do not add the default alias from config file")
@click.option("--title", "-t", help="A title for this version")
def deploy(version: str, title:Optional[str], alias: tuple[str]):
    """
    Deploy a version of your documentation

    VERSION: The version number to deploy as.

    TITLE: A name to give this version. If not set will default to VERSION
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    if config.effective_built_site is None:
        raise click.ClickException(f"No built site {'set' if config.built_site_pattern is None else 'found'}")
    target = target_for_url(target_url=config.effective_built_site)
    with ExitStack() as exit_stack:
        try:
            source = exit_stack.enter_context(source_for_url(source_url=config.effective_built_site))
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc))
        target_session = exit_stack.enter_context(target.start_session())
        actions.upload(source=source, target=target_session, version_id=version, title=title)
        for _alias in alias:
            actions.create_alias(
                target=target_session,
                alias_id=_alias,
                version=version,
                mechanisms=config.redirect_mechanisms,
            )


@main.command()
@click.argument("VERSION")
def delete_version(version: str):
    """
    Delete a version of your documentation and all aliases pointing to it.

    VERSION: The version number to deploy as.
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    with target.start_session() as target_session:
        actions.delete_version(target_session, version)


@main.command()
@click.argument("VERSION")
@click.argument("ALIAS")
def set_alias(version: str, alias: str):
    """
    Set an alias for a specific version, or add a redirect type for that alias.
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    with target.start_session() as target_session:
        actions.create_alias(
            target=target_session,
            alias_id=alias,
            version=version,
            mechanisms=config.redirect_mechanisms,
        )


@main.command()
@click.argument("ALIAS", required=False)
@click.option("--all-redirects-type", help="Delete all redirects for aliases of a specific alias type.")
def delete_alias(alias: Optional[str], all_redirects_type: Optional[str]):
    """
    Delete an alias or single redirection type.

    If ALIAS is set and not --redirect-type then the alias will be completely deleted and all redirects for it removed.

    If both ALIAS and --redirect-type are set then just one redirect will be removed of a single type.  The alias
    meta references to the alias will only be removed if it leaves no remaining redirects.

    --all-aliases Exists for preparation of site moves.
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    if all_redirects_type is not None:
        if alias is not None:
            raise click.ClickException("Cannot specify an ALIAS and --all-aliases")
        with target.start_session() as target_session:
            for alias_id, alias in target_session.deployment_spec.aliases.items():
                matching_mechanisms = [_type for _type in all_redirects_type if _type in alias.redirect_mechanisms]
                if matching_mechanisms:
                    actions.delete_alias(target=target_session, alias_id=alias_id, mechanisms=matching_mechanisms)
    if alias is not None:
        with target.start_session() as target_session:
            actions.delete_alias(target=target_session, alias_id=alias, mechanisms=None)
    else:
        raise click.ClickException("If ALIAS is not given both --all-redirects-type must be set")


@main.command()
@click.argument("VERSION")
def set_default(version: str):
    """
    Set the default version or alias for your site.

    This is very similar to an alias and makes use of redirect rules.
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    with target.start_session() as target_session:
        actions.create_alias(target_session, ..., version, config.redirect_mechanisms)


@main.command()
def unset_default():
    """
    Clear the default version or alias setting for your site.

    This is very similar to an alias and makes use of redirect rules.
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    with target.start_session() as target_session:
        actions.delete_alias(target_session, ..., None)


@main.command()
@click.option("--out-format", type=click.Choice(["plain", "json"]), help="Output format")
def describe(out_format: str):
    """
    Describe the current deployment setup of your software versions
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    target = target_for_url(target_url=config.deploy_url)
    with target.start_session() as target_session:
        if out_format == "json":
            print(target_session.deployment_spec.json(sort_keys=True, indent=True))
        if out_format == "yaml":
            yaml.safe_dump(to_jsonable_dict(target_session.deployment_spec.dict()), stream=sys.stdout)
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


@main.command()
def show_config():
    """
    Show the effective config after applying overrides and setting defaults
    """
    config: MkdocsDeployConfig = click.get_current_context().obj
    yaml.safe_dump(to_jsonable_dict(config.dict()), stream=sys.stdout)

# https://github.com/pydantic/pydantic/issues/1409#issuecomment-877175194
def to_jsonable_dict(obj):
    if isinstance(obj, dict):
        return {key: to_jsonable_dict(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [to_jsonable_dict(value) for value in obj]
    elif isinstance(obj, tuple):
        return tuple(to_jsonable_dict(value) for value in obj)
    elif isinstance(obj, JSONABLE_TYPES):
        return obj
    return pydantic.json.pydantic_encoder(obj)
