from typing import IO

import boto3

from .abstract import RedirectMechanism, Target, TargetSession
from .versions import Version


class S3Target(Target):

    def __init__(self, bucket: str, prefix_key: str, seperator: str = "/"):
        self._bucket = bucket
        self._prefix_key = prefix_key
        self._seperator = seperator

    def start_session(self) -> TargetSession:
        return S3TargetSession(self._bucket, self._prefix_key, self._seperator)


class S3TargetSession(TargetSession):

    def __init__(self, bucket: str, prefix_key: str, seperator: str = "/"):
        self._bucket = bucket
        self._prefix_key = prefix_key
        self._seperator = seperator

    def start_version(self, version_id: str) -> None:
        pass

    def upload_file(self, version_id: str, filename: str, file_obj: IO[bytes]) -> None:
        pass

    def get_redirect_mechanism(self, mechanism_name: str) -> RedirectMechanism:
        pass

    def close(self, success: bool = False) -> None:
        pass

    def version_meta(self, version: str) -> Version:
        pass

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
        key=parts.path[1:] if parts.path else ""
    )