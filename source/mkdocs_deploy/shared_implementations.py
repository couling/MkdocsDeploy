import contextlib
import logging
import os
from tempfile import SpooledTemporaryFile
from typing import IO

from .versions import DEPLOYMENTS_FILENAME, DeploymentSpec, MIKE_VERSIONS_FILENAME

_logger = logging.getLogger(__name__)


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
