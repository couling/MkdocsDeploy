from typing import Iterable

import boto3.session
import moto
import pytest


@pytest.fixture(autouse=True)
def default_region(monkeypatch: pytest.MonkeyPatch) -> str:
    region = "eu-west-2"
    monkeypatch.setenv("AWS_DEFAULT_REGION", region)
    return region


@pytest.fixture()
def s3_bucket(default_region: str) -> Iterable[str]:
    bucket_name = "test-bucket"
    with moto.mock_s3():
        client = boto3.client("s3")
        client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': default_region, # type: ignore
            }
        )
        yield bucket_name
