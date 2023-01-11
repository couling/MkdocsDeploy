"""
Written but currently not used in the codebase.
"""
from pathlib import Path
from urllib.parse import urlparse

import mkdocs.config.base
import mkdocs.config.config_options
import mkdocs.plugins

_CONFIG_EXTENSIONS = ("mkdocs.yaml", "mkdocs.yml")

class MkdocsDeployConfig(mkdocs.config.base.Config):
    target_url = mkdocs.config.config_options.Type(str, default=None)

    @property
    def bucket_and_key(self) -> tuple[str, str]:
        parts = urlparse(self.target_url)
        if parts.scheme != "s3":
            raise f"target_url must be s3 not {parts.scheme}"
        if not parts.hostname:
            raise ValueError("No hostname in S3 bucket")
        key = parts.path[1:] if parts.path is not None else ""
        bucket = parts.hostname
        assert isinstance(key, str)
        assert isinstance(bucket, str)
        return bucket, key


class MkdocsDeploy(mkdocs.plugins.BasePlugin[MkdocsDeployConfig]):
    ...


def load_config(config_file: Path):
    if config_file.is_dir():
        possible_files = [config_file / name for name in _CONFIG_EXTENSIONS]
        for file in possible_files:
            if file.is_file():
                config_file = file
                break
        else:
            raise FileNotFoundError(f"Cannot find config file {' or '.join(str(file) for file in possible_files)}")

    with open(config_file, "rb") as file_obj:
        cfg = mkdocs.config.load_config(file_obj,)
        result = cfg['plugins'].run_event('config', cfg)
        try:
            return result['plugins']['mkdocs-deploy']
        except KeyError as exc:
            raise ValueError("mkdocs-deploy is not enabled for this project.  Please update your config") from exc
