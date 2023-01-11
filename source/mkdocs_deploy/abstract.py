import urllib.parse
from abc import abstractmethod
from typing import Callable, IO, Iterable, Optional, Protocol

from .versions import DeploymentSpec, DeploymentAlias


class VersionNotFound(Exception):
    pass


class RedirectMechanismNotFound(Exception):
    pass


class Source(Protocol):
    """
    Source is where a site is loaded from.
    """

    @abstractmethod
    def iter_files(self) -> Iterable[str]:
        """
        Iterate over all files in the source
        :return: An Iterable of file names (relative file paths) in the source.
        These can be used with ``open_file_for_read``
        """

    @abstractmethod
    def open_file_for_read(self, filename:str) -> IO[bytes]:
        """
        Open a file by file name for reading.

        :param filename:  The file name (relative file path) of the file to open
        :return: An open file handle to read from.  The calling method is responsible for closing it.
        """

    def close(self) -> None:
        """
        Close any underlying resource handles
        """

    def __enter__(self):
        """
        No effect
        """
        return self

    def  __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close the Source
        """
        self.close()


class TargetSession(Protocol):
    """
    Target is the place sites are deployed to
    """

    @abstractmethod
    def start_version(self, version_id: str, title: str) -> None:
        """
        Prepare to write a new site version.

        This MUST have the ultimate effect of deleting any files in the version if it already existed and they are not
        replaced with ``TargetSession.upload_file()``.
        :param version_id: The id of the new version
        :param title: The version title.
        """

    @abstractmethod
    def delete_version(self, version_id: str) -> None:
        """
        Delete a whole version

        :param version_id: The version to delete
        """

    @abstractmethod
    def upload_file(self, version_id: str, filename: str, file_obj: IO[bytes]) -> None:
        """
        Upload a file to the target
        :param version_id: The site version you wish to upload to.
        :param filename: The filename of the file within the site version.
        :param file_obj: An open file handle to read data from.
        """

    @abstractmethod
    def download_file(self, version_id: str, filename: str) -> IO[bytes]:
        """
        Open a file handle to read content of a file
        :param version_id: The version for the site
        :param filename: The filename within that version (not including version_id)
        :return: An open file handle
        :raises FileNotFoundError: If the version did not contain the requested file
        :raises VersionNotFound: if the version_id did not exist
        """
        raise

    def delete_file(self, version_id: str, filename: str) -> None:
        """
        Delete a file, or mark it for deletion on close.
        :param version_id: The version to delete from
        :param filename: The filename to delete
        """

    @abstractmethod
    def iter_files(self, version_id: str) -> Iterable[str]:
        """
        Get an iterator over all file names in a version prefix.

        :param version_id: The version_id to fetch
        :return: An iterator containing every file name without version prefix
        :raises VersionNotFound: If version_id does not exist
        """

    @abstractmethod
    def close(self, success: bool = False) -> None:
        """
        Close any underlying resources
        :param success: Indicates if this is being closed for reasons of success (True) or failure (False).  If closing
        for failure, the target should attempt some cleanup.  Depending on the target this many not be totally perfect.
        :return:
        """

    @abstractmethod
    def set_alias(self, alias_id: str, alias: Optional[DeploymentAlias]) -> None:
        """
        Create or delete an alias.

        This only updates the meta information for the alias.  It does not apply redirect mechanisms.  The passed alias
        completely replaces any existing alias with the same ID.

        :param alias_id: The alias ID.  If None is passed then the alias is deleted (if it existed).
        :param alias: The specification of the alias
        """

    @property
    @abstractmethod
    def available_redirect_mechanisms(self) -> dict[str, "RedirectMechanism"]:
        """
        Get a dictionary of available redirect mechanisms for this endpoint.  Keys are the mechanism id, values are the
        RedirectMechanism to invoke.
        """

    @property
    @abstractmethod
    def deployment_spec(self) -> DeploymentSpec:
        """
        The deployments spec for this target having applied any operations.
        """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(success=exc_type is None)


class Target(Protocol):

    @abstractmethod
    def start_session(self) -> TargetSession:
        """
        Start a new session.

        This method primarily exists for targets like git where all changes are intended to go into a single git commit.
        Starting a session, and subsequently calling ``session.close(success=True)`` will ultimately result in just one
        git commit, not matter how many operations occurred in the single session.
        """


class RedirectMechanism(Protocol):
    """
    Implements a mechanism to redirect from one site version to another.
    """

    @abstractmethod
    def create_redirect(self, session: TargetSession, alias: str, version_id: str) -> None:
        """
        Create a redirect

        :param session: The TargetSession to apply changes to
        :param alias: The new alias to create.  If "" is passed, then a redirect from the root is created.  IE: ""
        defines what the default version is.
        :param version_id: The version to redirect to.
        """

    @abstractmethod
    def delete_redirect(self, session: TargetSession, alias: str) -> None:
        """
        Delete the named redirect.

        :param session: The TargetSession to apply changes to
        :param alias: The alias to delete
        """

    def refresh_redirect(self, session: TargetSession, alias: str, version_id: str) -> None:
        """
        Called to ensure all redirects still work after a version has been altered.

        :param session: The TargetSession to apply changes to
        :param alias: The alias to refresh
        :param version_id: The version to redirect to.
        """
        self.delete_redirect(session, alias)
        self.create_redirect(session, alias, version_id)


_SOURCES = {}

_TARGETS = {}


def register_source(source_scheme: str, source_class: Callable[[str], Source]) -> None:
    """
    Register a source type.

    :param source_scheme: The url scheme to associate this class with
    :param source_class: The class to register
    """
    _SOURCES[source_scheme] = source_class


def register_target(target_scheme: str, target_class: Callable[[str], Target]):
    """
    Register a target type.

    :param target_scheme: The url scheme to associate this class with
    :param target_class: The class to register
    """
    _TARGETS[target_scheme] = target_class


def source_for_url(source_url: str) -> Source:
    """
    Get a Source for a given URL
    :param source_url:
    :return:
    """
    handler = _SOURCES[urllib.parse.urlparse(source_url).scheme]
    return handler(source_url)


def target_for_url(target_url: str) -> Target:
    """
    Get a Target for a given URL
    :param target_url:
    :return:
    """
    handler = _TARGETS[urllib.parse.urlparse(target_url).scheme]
    return handler(target_url)