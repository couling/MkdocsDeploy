import contextlib
import copy
import json
import logging
import mimetypes
import tempfile
import urllib.parse
from typing import IO, Iterable, NamedTuple, Optional

import boto3
import botocore.exceptions

from . import local_filesystem
from .. import abstract, shared_implementations, versions

_logger = logging.getLogger(__name__)


def enable_plugin() -> None:
    """
    Enables the plugin.

    Registers s3:// urls as both source and target
    """
    abstract.register_source(source_scheme="s3", source_class=S3Source)
    abstract.register_target(target_scheme="s3", target_class=target_from_url)


class S3Source(contextlib.closing):

    def __init__(self, file_url: str):
        self._exit_stack = contextlib.ExitStack()
        super().__init__(self._exit_stack)
        object_details = s3_details_from_url(file_url)
        try:
            temp_file = self._exit_stack.enter_context(tempfile.TemporaryFile())
            s3 = boto3.client('s3')
            s3.download_fileobj(object_details.bucket, object_details.key, temp_file)
            self._wrapper = local_filesystem.open_file_obj_source(temp_file)
        except ValueError as exc:
            self._exit_stack.close()
            raise ValueError(f"Cannot open {file_url}") from exc
        except:
            self._exit_stack.close()
            raise

    def __getattr__(self, item: str):
        return getattr(self._wrapper, item)

    def close(self) -> None:
        self._exit_stack.close()


class S3TargetSession(abstract.TargetSession):

    def __init__(self, bucket: str, prefix_key: str, seperator: str = "/"):
        self._bucket = bucket
        self._prefix_key = prefix_key
        self._seperator = seperator
        self._client = boto3.client("s3")
        self._deployment_spec = self._load_deployments()
        self._changed = False

    def _load_deployments(self) -> versions.DeploymentSpec:
        try:
            result = self._client.get_object(
                Bucket=self._bucket,
                Key= self._prefix_key + versions.DEPLOYMENTS_FILENAME,
            )
            return versions.DeploymentSpec.parse_obj(json.load(result['Body']))
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'NoSuchKey':
                _logger.warning(
                    "%s does not exist in s3://%s/%s assuming this is a new site",
                     versions.DEPLOYMENTS_FILENAME,
                     self._bucket,
                     self._prefix_key,
                )
                return versions.DeploymentSpec()
            raise

    def start_version(self, version_id: str, title: str) -> None:
        self._deployment_spec.versions[version_id] = versions.DeploymentVersion(title=title)
        self._changed = True

    def upload_file(self, version_id: abstract.Version, filename: str, file_obj: IO[bytes]) -> None:
        extra_args = {}
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is not None:
            extra_args['ContentType'] = mime_type
        if not self._alias_or_version_exists(version_id):
            raise abstract.VersionNotFound(version_id)

        self._client.upload_fileobj(
            file_obj,
            self._bucket,
            self._key_for(version_id, filename),
            extra_args,
        )
        self._changed = True

    def delete_file(self, version_id: abstract.Version, filename: str) -> None:
        if not self._alias_or_version_exists(version_id):
            raise abstract.VersionNotFound(version_id)
        # No need to catch an exception here. If the object doesn't exist the call will succeed
        # https://stackoverflow.com/a/30698746/453851
        self._client.delete_object(Bucket=self._bucket, Key=self._key_for(version_id, filename))
        self._changed = True

    def close(self, success: bool = False) -> None:
        if success:
            if self._changed:
                meta_data = shared_implementations.generate_meta_data(self._deployment_spec)
                for filename, content in meta_data.items():
                    _logger.debug("Writing %s", filename)
                    self._client.put_object(
                        Bucket=self._bucket,
                        Key=self._prefix_key + filename,
                        Body=content,
                    )
            else:
                _logger.debug("No changes, not writing meta")
        else:
            _logger.warning("Not saving site meta due to error. Site might be in an inconsistent state")

    def delete_version_or_alias(self, version_id: str) -> None:
        if version_id is abstract.DEFAULT_VERSION:
            raise RuntimeError(
                "Attempt to delete the DEFAULT_VERSION. "
                "This must not happen: it would delete the entire site."
            )
        if not self._alias_or_version_exists(version_id):
            raise abstract.VersionNotFound(version_id)
        self._changed = True
        self._clean_directory(version_id)
        self._deployment_spec.versions.pop(version_id, None)
        self._deployment_spec.aliases.pop(version_id, None)

    def _clean_directory(self, version_id: str) -> None:
        for file in self.iter_files(version_id=version_id):
            self.delete_file(version_id, file)

    def download_file(self, version_id: abstract.Version, filename: str) -> IO[bytes]:
        if not self._alias_or_version_exists(version_id):
            raise abstract.VersionNotFound(version_id)
        try:
            result = self._client.get_object(Bucket=self._bucket, Key=self._key_for(version_id, filename))
            return result['Body']
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(self._key_for(version_id, filename)) from exc

    def iter_files(self, version_id: abstract.Version) -> Iterable[str]:
        paginator = self._client.get_paginator('list_objects_v2')
        prefix = self._key_for(version_id, "")
        if version_id is abstract.DEFAULT_VERSION:
            results = paginator.paginate(Bucket=self._bucket, Prefix=prefix, Delimiter="/")
        else:
            results = paginator.paginate(Bucket=self._bucket, Prefix=prefix)
        for page in results:
            for file in page.get('Contents', ()):
                yield file['Key'][len(prefix):]

    def set_alias(self, alias_id: abstract.Version, alias: versions.DeploymentAlias) -> None:
        alias = copy.deepcopy(alias)
        if alias_id is abstract.DEFAULT_VERSION:
            self._deployment_spec.default_version = alias
        else:
            self._deployment_spec.aliases[alias_id] = alias
        self._changed = True

    @property
    def available_redirect_mechanisms(self) -> dict[str, abstract.RedirectMechanism]:
        # TODO add S3 redirect
        # TODO cloud front redirect rules
        return {}

    @property
    def deployment_spec(self) -> versions.DeploymentSpec:
        return copy.deepcopy(self._deployment_spec)

    def _key_for(self, version_id: abstract.Version, filename: str) -> str:
        if version_id is abstract.DEFAULT_VERSION:
            if "/" in filename:
                raise ValueError(f"filename must not contain '/' if version_id is DEFAULT_VERSION: {filename}")
            return self._prefix_key + filename
        return f"{self._prefix_key}{version_id}/{filename}"

    def _alias_or_version_exists(self, version_id: abstract.Version) -> bool:
        if version_id is abstract.DEFAULT_VERSION:
            return True
        return version_id in self._deployment_spec.versions or version_id in self._deployment_spec.aliases


class S3Target(abstract.Target):

    def __init__(self, bucket: str, prefix_key: str, seperator: str = "/"):
        self._bucket = bucket
        if prefix_key and not prefix_key[-1] == seperator:
            prefix_key += seperator
        self._prefix_key = prefix_key
        self._seperator = seperator

    def start_session(self) -> S3TargetSession:
        return S3TargetSession(self._bucket, self._prefix_key, self._seperator)


def target_from_url(url: str) -> "S3Target":
    details = s3_details_from_url(url)
    return S3Target(details.bucket, details.key)


class S3Details(NamedTuple):
    bucket: str
    key: str


def s3_details_from_url(url: str) -> S3Details:
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "s3":
        raise ValueError(f"Not a valid S3 URL. Expecting scheme S3 got {parts.scheme} in {url}")
    if not parts.hostname:
        raise ValueError(f"Not a valid S3 URL. No hostname therefore no bucket name in {url}")
    return S3Details(
        bucket=parts.hostname,
        key=parts.path[1:] if parts.path else "",
    )
