import contextlib
import logging
import os
from tempfile import SpooledTemporaryFile
from typing import IO
from urllib.parse import quote
from .versions import DEPLOYMENTS_FILENAME, DeploymentSpec, MIKE_VERSIONS_FILENAME

_logger = logging.getLogger(__name__)


def is_index_file(file_name: str) -> bool:
    """Check if a filename is an index file

    Test if a filename is an index.htm or index.html file in any directory
    :param file_name: Filename to test
    :return: True if filename is an index file or False otherwise"""
    if file_name in ("index.htm", "index.html"):
        return True
    if file_name.endswith("/index.htm") or file_name.endswith("/index.html"):
        return True
    return False


def relative_link(
    target_version: str,
    target_file_name: str,
    *,
    source_file_name: str | None = None,
    from_root: bool = False,
) -> str:
    """Generate a relative link for a filename

    The origin is assumed to be a file of the same name, meaning
    :param target_version: The version target for the link
    :param target_file_name: The file name to link to
    :param source_file_name: The filename the link will be relative to.  If None, and if from_root is not set, then
        source_file_name will default to target_file_name and assume.  This is useful for generating an alias
        of a file name
    :param from_root: If True, the relative link is generated from the root of the documentation and source_file_name
        is ignored.
        If False, the relative link is generated relative to a file in the same directory in another version.
        It doesn't matter which other version since the result is always just adding "../"
    :return: An url escaped relative path
    """
    url = "/" + quote(target_file_name, safe="/")
    if is_index_file(target_file_name):
        parts = url.split("/")
        parts[-1] = ""
        url = "/".join(parts)
    if from_root:
        relative = ""
    else:
        if source_file_name is None:
            source_file_name = target_file_name
        relative = "../" * len(source_file_name.split("/"))
    return relative + target_version + url


def generate_meta_data(deployment_spec: DeploymentSpec) -> dict[str, bytes]:
    """
    Generate metadata files to write at the root of a site.

    This just creates a dict with the filenames and content to write to them as bytes.
    At present this is just deployments.json and versions.json.  More may be added in the future.
    :param deployment_spec: The deployment spec to covert to files.
    :return: A dictionary with filenames as keys and the bytes to write to them
    """
    return {
        DEPLOYMENTS_FILENAME: deployment_spec.json().encode("utf-8"),
        MIKE_VERSIONS_FILENAME: deployment_spec.mike_versions().json().encode("utf-8"),
    }


class SeekableFileWrapper(contextlib.closing):
    """
    Acts as a wrapper on IO[bytes] which should always be seekable.

    This is particularly useful when trying to take an IO[bytes] from an unknown source and send it to target that needs
    to be seekable.  The source might be a local file, or might be downloaded over HTTP and thus be a non-seekable
    stream, but when the source opens the file it's unclear what will be done with it and if it needs to take special
    action to make it seekable.  So this wrapper can be used in a position in code where you NEED a seekable
    ``IO[bytes]`` but are unsure if you have one or not.

    This wrapper first tries to ``file.seek(file.tell(), os.SEEK_SET)``. This should have no effect on files which are
    seekable, but will raise an error if they are not seekable, for example if they are a stream.  Non-seekable files
    are then immediately read entirely into memory or a temporary file (if greater than 100KiB).

    Calling code is responsible for closing the wrapped file **after** it has closed this SeekableFileWrapper.

    Calling code should not make any assumptions about which operations such as read() or seek() will directly reach the
    wrapped file.  This the tell()
    """

    def __init__(self, file_to_wrap: IO[bytes]):
        """
        :param file_to_wrap: The underlying file to wrap.
        """
        self.__exit_stack = contextlib.ExitStack()
        super().__init__(self)
        try:
            file_to_wrap.seek(file_to_wrap.tell(), os.SEEK_SET)
        except Exception as exc:
            # I think catching Exception is appropriate due to the unpredictable nature of the exception we may get
            _logger.debug("File not seekable caching.  Due to: %s", str(exc))
            position = file_to_wrap.tell()
            seekable = self.__exit_stack.enter_context(SpooledTemporaryFile(max_size=102400))
            seekable.seek(position, os.SEEK_SET)
            while bytes_read := file_to_wrap.read(102400):
                seekable.write(bytes_read)
            seekable.seek(0, os.SEEK_SET)
            self.__wrapped_file = seekable
        else:
            self.__wrapped_file = file_to_wrap

    def __getattr__(self, item: str):
        return self.__wrapped_file.__getattribute__(item)

    def close(self) -> None:
        self.__exit_stack.close()
