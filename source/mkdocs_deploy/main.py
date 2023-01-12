from typing import Optional

import logging
import click
import sys

from . import actions
from .abstract import source_for_url, target_for_url
from contextlib import ExitStack


_LOG_FORMAT = "%(levelname)s: %(message)s"
_DEBUG_FORMAT = "%(levelname)s: %(name)s:  %(message)s"

@click.group()
@click.option("--log-level", help="Set log level", default="INFO")
def main(log_level: str):
    """
    Version aware Mkdocs deployment tool.
    """
    numeric_level = logging.getLevelName(log_level)
    if not isinstance(numeric_level, int):
        raise click.ClickException(f"Unknown log level {log_level}")
    logging.basicConfig(
        stream=sys.stdout,
        level=numeric_level,
        format=_LOG_FORMAT if numeric_level >= logging.INFO else _DEBUG_FORMAT,
    )
    actions.load_plugins()

@main.command()
@click.argument("SITE")
@click.argument("TARGET_URL")
@click.argument("VERSION")
@click.option("--alias", multiple=True, help="An alias to give the version")
@click.option("--title", help="A title to give the version")
def deploy(site: str, version: str, target_url: str, title:Optional[str], alias: tuple[str]):
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
            actions.create_alias(target=target_session, alias_id=_alias, version=version)


@main.command()
@click.argument("TARGET_URL")
@click.argument("VERSION")
def tear_down(version: str, target_url: str):
    """
    Remove a version of your documentation

    VERSION: The version number to deploy as.
    TARGET_URL: Where the site is to be published excluding the version number
    """
    target = target_for_url(target_url=target_url)
    with target.start_session() as target_session:
        actions.delete_version(target_session, version)

