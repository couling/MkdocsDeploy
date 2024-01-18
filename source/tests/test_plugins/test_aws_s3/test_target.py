import io
import itertools
import uuid
from copy import deepcopy

import boto3
import mypy_boto3_s3.type_defs
import pytest
from mypy_boto3_s3.client import S3Client

from mkdocs_deploy import abstract, shared_implementations, versions
from mkdocs_deploy.plugins import aws_s3


@pytest.fixture()
def target_prefix() -> str:
    return  "static-html/"

@pytest.fixture()
def s3_target(s3_bucket: str, target_prefix: str) -> aws_s3.S3Target:
    return aws_s3.S3Target(
        bucket=s3_bucket,
        prefix_key=target_prefix,
        seperator="/",
    )

@pytest.fixture(
    ids=["No_Existing_Spec", "Empty_Existing_Spec", "Populated_Existing_Spec"],
    params=[
        None,
        versions.DeploymentSpec(),
        versions.DeploymentSpec(
            default_version=versions.DeploymentAlias(version_id="latest", redirect_mechanisms={"html"}),
            versions={
                "1.0": versions.DeploymentVersion(title="Version 1"),
                "1.1": versions.DeploymentVersion(title="Version 1"),
            },
            aliases={
                "latest": versions.DeploymentAlias(version_id="1.1", redirect_mechanisms={"html"}),
            }
        )
    ],
)
def existing_site(s3_bucket: str, target_prefix: str, request) -> versions.DeploymentSpec | None:
    existing_site: versions.DeploymentSpec | None = request.param
    upload_whole_site(s3_bucket, target_prefix, existing_site)
    return deepcopy(existing_site)


def upload_whole_site(s3_bucket: str, target_prefix: str, site_spec: versions.DeploymentSpec | None):

    if site_spec is None:
        return None
    metadata = shared_implementations.generate_meta_data(site_spec)
    client = boto3.client("s3")
    # Initialise the bucket with the site's metadata
    for filename, content in metadata.items():
        client.put_object(Bucket=s3_bucket, Key=target_prefix + filename, Body=content)
    # Put a dummy index.html file for every version and alias:
    for key in itertools.chain(site_spec.versions, site_spec.aliases):
        client.put_object(Bucket=s3_bucket, Key=target_prefix + key + "/index.html", Body=b"")
    if site_spec.default_version:
        client.put_object(Bucket=s3_bucket, Key=target_prefix + "index.html", Body=b"")


def test_enable_plugin(s3_bucket: str, existing_site):
    aws_s3.enable_plugin()

    assert isinstance(abstract.target_for_url(f"s3://{s3_bucket}/"), aws_s3.S3Target)


def test_target_creates_matching_target_session(s3_target: aws_s3.S3Target, existing_site):
    result = s3_target.start_session()

    assert isinstance(result, aws_s3.S3TargetSession)

    assert result._bucket == s3_target._bucket
    assert result._prefix_key == s3_target._prefix_key
    assert result._seperator == s3_target._seperator


def test_target_creates_nothing_initially(s3_bucket: str, target_prefix: str):
    _ = aws_s3.S3Target(bucket=s3_bucket, prefix_key=target_prefix)
    client: S3Client = boto3.client("s3")
    # Don't care about pagination will fail the test if even one result comes back
    objects = client.list_objects_v2(Bucket=s3_bucket)
    assert "Contents" not in objects


def test_closing_session_on_empty_site_saves_nothing(s3_target: aws_s3.S3Target, s3_bucket: str, target_prefix: str):
    s3_target_session = s3_target.start_session()
    s3_target_session.close(success=True)
    client: S3Client = boto3.client("s3")
    # Don't care about pagination will fail the test if even one result comes back
    objects = client.list_objects_v2(Bucket=s3_bucket)
    assert "Contents" not in objects


def test_start_version_flags_changed(s3_target: aws_s3.S3Target, existing_site):
    s3_target_session = s3_target.start_session()
    assert not s3_target_session._changed
    s3_target_session.start_version("3.0", "Version 3")
    assert s3_target_session._changed


def test_start_version_creates_version_in_deployment_spec(existing_site, s3_target: aws_s3.S3Target):
    s3_target_session = s3_target.start_session()
    s3_target_session.start_version("3.0", "Version 3")
    assert s3_target_session.deployment_spec.versions["3.0"] == versions.DeploymentVersion(title="Version 3")


def test_close_success_saves_metadata(
    s3_target: aws_s3.S3Target,
    s3_bucket: str,
    target_prefix: str,
    existing_site: versions.DeploymentSpec | None,
):
    s3_target_session = s3_target.start_session()
    if existing_site is None:
        existing_site = versions.DeploymentSpec()
    existing_site.versions["3.0"] = versions.DeploymentVersion(title="Version 3")
    # Sanity check
    # Mutating existing_site in the line above should not change the session since metadat should have been loaded
    # and stored in a separate object.
    assert "3.0" not in s3_target_session.deployment_spec.versions
    s3_target_session.start_version("3.0", "Version 3")
    # Sanity check, starting a version should add it to the deployment spec
    assert "3.0" in s3_target_session.deployment_spec.versions

    s3_target_session.close(success=True)

    expected_result = shared_implementations.generate_meta_data(existing_site)
    client = boto3.client("s3")
    for filename, expected_content in expected_result.items():
        result = client.get_object(Bucket=s3_bucket, Key=target_prefix + filename)
        actual_content = result["Body"].read()
        assert expected_content == actual_content


def test_close_non_success_does_not_save_metadata(
    s3_target: aws_s3.S3Target,
    s3_bucket: str,
    target_prefix: str,
    existing_site: versions.DeploymentSpec | None,
):
    s3_target_session = s3_target.start_session()
    s3_target_session.start_version("3.0", "Version 3")
    # Sanity check, starting a version should add it to the deployment spec
    assert "3.0" in s3_target_session.deployment_spec.versions

    s3_target_session.close(success=False)

    client = boto3.client("s3")
    if existing_site is None:
        for filename in shared_implementations.generate_meta_data(s3_target_session.deployment_spec):
            with pytest.raises(client.exceptions.NoSuchKey):
                result = client.get_object(Bucket=s3_bucket, Key=target_prefix + filename)
                result["Body"].close()
    else:
        assert "3.0" not in existing_site.versions
        expected_result = shared_implementations.generate_meta_data(existing_site)
        avoid_result = shared_implementations.generate_meta_data(s3_target_session.deployment_spec)

        for filename, expected_content in expected_result.items():
            result = client.get_object(Bucket=s3_bucket, Key=target_prefix + filename)
            actual_content = result["Body"].read()
            # Be sure that expected_content != avoid_content.  Adding version 3.0 should ensure this.
            assert actual_content == expected_content
            assert actual_content != avoid_result[filename]


@pytest.mark.parametrize(("filename", "content_type"), [
    ("foo.txt", "text/plain"),
    ("foo.html", "text/html"),
    ("foo.jpeg", "image/jpeg"),
], ids=["text", "html", "image"])
def test_upload_file(
        s3_target: aws_s3.S3Target,
        alias: abstract.Version,
        filename: str,
        content_type: str,
        s3_bucket: str,
        target_prefix: str,
        existing_site,
):
    s3_target_session = s3_target.start_session()
    content = uuid.uuid4().bytes
    if alias is not abstract.DEFAULT_VERSION:
        s3_target_session.start_version(alias, alias)
    s3_target_session.upload_file(version_id=alias, filename=filename, file_obj=io.BytesIO(content))
    client = boto3.client("s3")
    key = target_prefix + filename if alias is abstract.DEFAULT_VERSION else target_prefix + alias + "/" + filename
    uploaded_object: mypy_boto3_s3.type_defs.GetObjectOutputTypeDef = client.get_object(Bucket=s3_bucket, Key=key)
    assert uploaded_object["Body"].read() == content
    assert uploaded_object["ContentType"] == content_type


def test_upload_file_fails_if_version_doesnt_exist(s3_target: aws_s3.S3Target):
    s3_target_session = s3_target.start_session()
    with pytest.raises(abstract.VersionNotFound):
        s3_target_session.upload_file(version_id="does not exist", filename="foo.txt", file_obj=io.BytesIO())


def test_delete_file(s3_target: aws_s3.S3Target, alias: abstract.Version, s3_bucket: str, target_prefix: str):
    s3_target_session = s3_target.start_session()
    if alias is not abstract.DEFAULT_VERSION:
        s3_target_session.start_version(alias, alias)
        key = f"{target_prefix}{alias}/foo.txt"
    else:
        key = f"{target_prefix}foo.txt"
    client = boto3.client("s3")
    client.put_object(Bucket=s3_bucket, Key=key, Body=b"hello world")

    s3_target_session.delete_file(alias, "foo.txt")

    # Make sure it's gone
    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket=s3_bucket, Key=key)


def test_delete_file_raises_version_not_found(s3_target: aws_s3.S3Target):
    s3_target_session = s3_target.start_session()
    with pytest.raises(abstract.VersionNotFound):
        s3_target_session.delete_file("version doesn't exist", "don't care.txt")


def test_deleting_default_version_is_impossible(s3_target: aws_s3.S3Target):
    s3_target_session = s3_target.start_session()
    with pytest.raises(RuntimeError):
        s3_target_session.delete_version_or_alias(
            version_id=abstract.DEFAULT_VERSION  # type: ignore
        )


def test_deleting_non_existent_version_raises_version_not_found(s3_target: aws_s3.S3Target):
    s3_target_session = s3_target.start_session()
    with pytest.raises(abstract.VersionNotFound):
        s3_target_session.delete_version_or_alias(version_id="Version does not exist")

def test_delete_entire_version(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    site_spec = versions.DeploymentSpec(
        default_version=versions.DeploymentAlias(version_id="latest", redirect_mechanisms={"html"}),
        versions={
            "1.0": versions.DeploymentVersion(title="First version"),
            "1.1": versions.DeploymentVersion(title="Patch 1"),
        },
        aliases={
            "latest": versions.DeploymentAlias(version_id="1.1", redirect_mechanisms={"html"}),
        }
    )
    upload_whole_site(s3_bucket, target_prefix, site_spec)

    # Session creation must happen after uploading the site
    s3_target_session = s3_target.start_session()

    s3_target_session.delete_version_or_alias("1.0")

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    keys = set()
    for page in paginator.paginate(Bucket=s3_bucket, Prefix=target_prefix, Delimiter="/"):
        for item in page["Contents"]:
            keys.add(item["Key"])
        for prefix in page["CommonPrefixes"]:
            keys.add(prefix["Prefix"])

    assert target_prefix + "1.0/" not in keys
    assert target_prefix + "1.1/" in keys
    assert target_prefix + "latest/" in keys
    assert target_prefix + "index.html" in keys


def test_download_returns_file_contents(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    site_spec = versions.DeploymentSpec(versions={"1.0": versions.DeploymentVersion(title="First version")})
    upload_whole_site(s3_bucket, target_prefix, site_spec)
    content = uuid.uuid4().bytes
    client = boto3.client("s3")
    key=f"{target_prefix}1.0/foo.txt"
    client.put_object(Bucket=s3_bucket, Key=key, Body=content)

    s3_target_session = s3_target.start_session()
    with s3_target_session.download_file("1.0", "foo.txt") as file_handle:
        uploaded_content = file_handle.read()

    assert uploaded_content == content


def test_download_missing_raises_file_not_found(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    site_spec = versions.DeploymentSpec(versions={"1.0": versions.DeploymentVersion(title="First version")})
    upload_whole_site(s3_bucket, target_prefix, site_spec)

    s3_target_session = s3_target.start_session()
    with pytest.raises(FileNotFoundError):
        with s3_target_session.download_file("1.0", "foo.txt"):
            pass


def test_download_from_missing_version(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    s3_target_session = s3_target.start_session()
    with pytest.raises(abstract.VersionNotFound):
        with s3_target_session.download_file("does not exist", "foo.txt"):
            pass


def test_iter_files_for_version(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    alias = "1.1"
    s3_target_session = s3_target.start_session()
    s3_target_session.start_version(alias, alias)
    client = boto3.client("s3")
    client.put_object(Bucket=s3_bucket, Key=target_prefix + "other/bar/a.txt", Body=b"HelloWorld")
    client.put_object(Bucket=s3_bucket, Key=target_prefix + alias + "/foo/b.txt", Body=b"HelloWorld")

    all_files = list(s3_target_session.iter_files(alias))
    assert all_files == ["foo/b.txt"]


def test_iter_files_for_default(s3_target: aws_s3.S3Target, s3_bucket:str, target_prefix: str):
    s3_target_session = s3_target.start_session()

    client = boto3.client("s3")
    client.put_object(Bucket=s3_bucket, Key=target_prefix + "a.txt", Body=b"HelloWorld")
    client.put_object(Bucket=s3_bucket, Key=target_prefix + "other/bar/b.txt", Body=b"HelloWorld")

    all_files = list(s3_target_session.iter_files(abstract.DEFAULT_VERSION))
    assert all_files == ["a.txt"]