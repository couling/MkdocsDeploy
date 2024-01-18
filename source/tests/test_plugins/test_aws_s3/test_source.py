import pytest

from mkdocs_deploy import abstract
from mkdocs_deploy.plugins import aws_s3

@pytest.mark.skip(reason="S3 Source is known to be broken right now")
def test_enable_plugin(s3_bucket: str):
    aws_s3.enable_plugin()

    assert isinstance(abstract.source_for_url(f"s3://{s3_bucket}/"), aws_s3.S3Source)
