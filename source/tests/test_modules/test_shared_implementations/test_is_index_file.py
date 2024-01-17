import pytest

from mkdocs_deploy.shared_implementations import is_index_file


@pytest.mark.parametrize("file_name", ["index.html", "index.htm", "bar/index.htm", "foo/index.html"])
def test_is_index_file(file_name: str):
    assert is_index_file(file_name)


@pytest.mark.parametrize("file_name", ["foo", "foo/bar/", "baz\\index.html", "bob_index.html"])
def test_is_not_index_file(file_name: str):
    assert not is_index_file(file_name)
