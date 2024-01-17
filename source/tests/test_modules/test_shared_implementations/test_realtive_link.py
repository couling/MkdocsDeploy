import pytest

from mkdocs_deploy.shared_implementations import relative_link

VERSION = "1.4.3"


@pytest.mark.parametrize(("file_name", "link"), [
    ("index.html", f"{VERSION}/"),
    ("foo/index.html", f"{VERSION}/foo/"),
    ("foo_index.html", f"{VERSION}/foo_index.html"),
    ("foo index.html", f"{VERSION}/foo%20index.html"),
])
def test_root_link(file_name: str, link: str):
    assert relative_link(VERSION, file_name, from_root=True) == link


@pytest.mark.parametrize(("file_name", "link"),  [
    ("index.html", f"../{VERSION}/"),
    ("foo/index.html", f"../../{VERSION}/foo/"),
    ("foo_index.html", f"../{VERSION}/foo_index.html"),
    ("foo index.html", f"../{VERSION}/foo%20index.html"),
])
def test_version_link(file_name: str, link: str):
    assert relative_link(VERSION, file_name) == link


@pytest.mark.parametrize(("file_name", "source_file_name", "link"),  [
    ("index.html", "index.html", f"../{VERSION}/"),
    ("index.html", "", f"../{VERSION}/"),
    ("foo/index.html", "index.html", f"../{VERSION}/foo/"),
    ("foo/index.html", "bar/index.html", f"../../{VERSION}/foo/"),
    ("foo/index.html", "bar/baz/index.html", f"../../../{VERSION}/foo/"),
    ("foo/index.html", "bar/", f"../../{VERSION}/foo/"),
])
def test_explicit_source_file(file_name: str, source_file_name: str, link: str):
    assert relative_link(VERSION, file_name, source_file_name=source_file_name) == link


@pytest.mark.parametrize(("file_name", "source_file_name", "link"),  [
    ("index.html", "index.html", f"{VERSION}/"),
    ("index.html", "", f"{VERSION}/"),
    ("foo/index.html", "index.html", f"{VERSION}/foo/"),
    ("foo/index.html", "bar/index.html", f"{VERSION}/foo/"),
    ("foo/index.html", "bar/baz/index.html", f"{VERSION}/foo/"),
    ("foo/index.html", "bar/", f"{VERSION}/foo/"),
])
def test_explicit_source_file_ignored_on_root(file_name: str, source_file_name: str, link: str):
    assert relative_link(VERSION, file_name, source_file_name=source_file_name, from_root=True) == link
