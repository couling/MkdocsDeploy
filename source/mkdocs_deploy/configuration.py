import glob
import json
import logging
from pathlib import Path
from typing import Callable, NamedTuple, Optional

import pydantic
import toml
import yaml

logger = logging.getLogger(__name__)


class MkdocsDeployConfig(pydantic.BaseModel):
    """Configuration for mkdocs-deploy"""
    config_base_dir: Path
    """Config base dir"""

    built_site: Optional[str] = None
    """Fixed url where to find the built mkdocs site ready to deploy
    
    One of ``build_url`` and ``build_pattern`` may be specified not both.
    
    This can be just a local path without ``file:///```"""

    built_site_pattern: Optional[str] = None
    """Glob pattern to where to find the built mkdocs site ready to deploy.
     
    Relative paths will be interpreted relative to the configuration file.
    
    One of ``build_url`` and ``build_pattern`` may be specified not both."""

    deploy_url: Optional[str] = None
    """URL to deploy to"""

    default_aliases: list[str] = ["latest"]
    """List of aliases to add if none specified"""

    redirect_mechanisms: list[str] = ["html"]
    """List of alias types to use if not otherwise specified"""

    _effective_built_site: Optional[str] = None

    @property
    def effective_built_site(self) -> Optional[str]:
        """Evaluates built_site and build_site_pattern to find the built site"""
        if self._effective_built_site is None:
            if self.built_site_pattern is not None:
                file_paths = sorted(
                    glob.glob(
                        self.built_site_pattern,
                        root_dir=self.config_base_dir,
                        recursive=True,
                        include_hidden=False,
                    )
                )
                if file_paths:
                    self._effective_built_site = file_paths[0]
            else:
                self._effective_built_site = self.built_site
        return self._effective_built_site


class ConfigurationSource(NamedTuple):
    """Configuration source"""
    file_name: str
    """Filename this source works with"""
    read: Callable[[Path], Optional[dict]]
    """Function to parse this file"""


def find_configuration() -> MkdocsDeployConfig:
    """Find a configuration file which contains configuration directives"""
    current_path = Path(".").resolve()
    logging.debug("Looking for config in %s", current_path)
    while True:
        for source in _configuration_sources:
            file_path = current_path / source.file_name
            if file_path.exists():
                logger.debug("Found %s", file_path)
                result = source.read(current_path / source.file_name)
                if result:
                    logger.info("Found configuration in %s", file_path)
                    result.setdefault("config_base_dir", file_path.parent)
                    return MkdocsDeployConfig.parse_obj(result)
                logger.debug("No configuration found in %s, continue searching", file_path)
        next_path = (current_path / "..").resolve()
        if next_path == current_path:
            break
        current_path = next_path
    return MkdocsDeployConfig(config_base_dir=Path("."))


def load_configuration(config_path: Path) -> MkdocsDeployConfig:
    """Load configuration from a specific path

    :param config_path: The file to load. This MUST exist
    :returns: Loaded configuration"""
    for configuration_source in _configuration_sources:
        if configuration_source.file_name == config_path.name:
            config_dict = configuration_source.read(config_path)
            if config_dict is None:
                logger.warning("No configuration found in %s", config_path)
                return MkdocsDeployConfig(config_base_dir=Path("."))
            config_dict.setdefault("config_base_dir", config_path.parent)
            return MkdocsDeployConfig.parse_obj(config_dict)


def _load_toml_file(file_path: Path) -> Optional[dict]:
    return toml.load(file_path).get("tool", {}).get("mkdocs-deploy", None)


def _load_yaml_file(file_path: Path) -> dict:
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def _load_json_file(file_path: Path) -> dict:
    with open(file_path, "r") as file:
        return json.load(file)


_configuration_sources: list[ConfigurationSource] = [
    ConfigurationSource("mkdocs-deploy.json", _load_json_file),
    ConfigurationSource("mkdocs-deploy.yaml",  _load_yaml_file),
    ConfigurationSource("pyproject.toml", _load_toml_file),
]


def add_configuration_source(new_source: ConfigurationSource) -> None:
    """Add a new configuration source

    This is useful for plugins to add additional configuration sources
    :param new_source: New source to add
    """
    _configuration_sources.append(new_source)
