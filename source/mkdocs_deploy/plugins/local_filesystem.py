import logging
import os
import tarfile
import urllib.parse
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import IO, Iterable, Optional, Union

from .. import abstract, shared_implementations
from ..versions import DeploymentAlias, DeploymentSpec, DeploymentVersion

LOCAL_FILE_REDIRECT_MECHANISMS = shared_implementations.SHARED_REDIRECT_MECHANISMS.copy()

_logger = logging.getLogger(__name__)


def enable_plugin() -> None:
    """
    Enables the plugin.

    Registers source and target for scheme "file" and "".
    """
    abstract.register_source(source_scheme="", source_class=open_source)
    abstract.register_source(source_scheme="file", source_class=open_source)
    abstract.register_target(target_scheme="", target_class=LocalFileTreeTarget)
    abstract.register_target(target_scheme="file", target_class=LocalFileTreeTarget)


class LocalFileTreeSource(abstract.Source):

    def __init__(self, file_path: Union[Path]):
        self._file_path = file_path

    def iter_files(self) -> Iterable[str]:
        return self._iter_files(self._file_path)

    def _iter_files(self, file_path: Path) -> Iterable[str]:
        for file in file_path.iterdir():
            if file.is_file():
                yield str(file.relative_to(self._file_path))
            elif file.is_dir():
                yield from self._iter_files(file)

    def open_file_for_read(self, filename: str) -> IO[bytes]:
        return open(self._file_path / filename, "rb")


class TarSource(abstract.Source):

    def __init__(self, file_path: Union[Path, IO[bytes]], prefix: str = "site/"):
        super().__init__()
        self._prefix = prefix
        if isinstance(file_path, (str, Path)):
            self._tar_file = tarfile.open(name=file_path, mode="r")
        else:
            self._tar_file = tarfile.open(fileobj=file_path, mode="r")
        self._file_path = file_path

    def iter_files(self) -> Iterable[str]:
        for file in self._tar_file.getmembers():
            if file.isreg() and file.name.startswith(self._prefix):
                yield file.name[len(self._prefix):]

    def open_file_for_read(self, filename: str) -> IO[bytes]:
        result = self._tar_file.extractfile(self._prefix + filename)
        if result is None:
            raise RuntimeError(f"Requested file is not a regular file: {filename} in {self._file_path}")

    def close(self):
        self._tar_file.close()



class ZipSource(abstract.Source):

    def __init__(self, file_path: Union[Path, IO[bytes]], prefix: str = "site/"):
        super().__init__()
        self._prefix = prefix
        self._zip_file = zipfile.ZipFile(file_path, "r")

    def iter_files(self) -> Iterable[str]:
        for file in self._zip_file.filelist:
            if file.filename.startswith(self._prefix):
                yield file.filename[len(self._prefix):]

    def open_file_for_read(self, filename: str) -> IO[bytes]:
        return self._zip_file.open(self._prefix + filename, "r")

    def close(self):
        self._zip_file.close()


def open_source(path: str) -> abstract.Source:
    """
    Open a local source.  Will
    """
    path = _path_from_url(path)
    if path.is_dir():
        return LocalFileTreeSource(path)

    file = open(path, "rb")
    try:
        return open_file_obj_source(file)
    except ValueError as exc:
        file.close()
        raise ValueError(f"Unable to open {path}") from exc.__context__
    except:
        file.close()
        raise


def open_file_obj_source(file: IO[bytes]) -> abstract.Source:
    """
    Open a file object as a source

    Supports both zip and tar.  You do not need to tell it which one, it will figure it out for you.

    The caller is responsible for closing the source
    :param file: An open file handle to a .zip or .tar.[|.gz|.bz2|.xz]
    :return: A file source to read from that file
    """
    try:
        file.seek(0, os.SEEK_SET)
        return ZipSource(file)
    except zipfile.BadZipfile as exc:
        _logger.debug("Cannot open as zip: %s", str(exc))
        try:
            file.seek(0, os.SEEK_SET)
            return TarSource(file)
        except tarfile.ReadError as exc:
            _logger.debug("Cannot open as zip: %s", str(exc))
            raise ValueError("Cannot open as tar")


def _path_from_url(url: str) -> Path:
    if "://" in url:
        return Path((url.path or "")[1:])
    return Path(url)


class LocalFileTreeTargetSession(abstract.TargetSession):

    def __init__(self, target_path: Path):
        self._target_path = target_path.resolve()
        try:
            self._deployment_spec = DeploymentSpec.parse_file(self._target_path / 'deployments.json')
        except FileNotFoundError:
            # TODO attempt to parse versions.json instead.
            self._deployment_spec = DeploymentSpec()
        self._changed = False

    def start_version(self, version_id: str, title: str) -> None:
        if version_id in self._deployment_spec.aliases:
            raise ValueError(f"Cannot create a version with the same name as an alias. "
                             f"Delete the alias first: {version_id}")
        if version_id not in self._deployment_spec.versions:
            self._deployment_spec.versions[version_id] = DeploymentVersion(title=title)
        else:
            # If there is other meta, we don't really want to overwrite it here.
            # It seems pragmatic to roll over old meta.
            # I guess this decision might change if someone has a burning reason to start new every time.
            self._deployment_spec.versions[version_id].title = title
        self._changed = True
        version_path = self._path_for_file(version_id)
        # Ensure the path is clean with no junk left behind for previous failure
        _recursive_delete(version_path)
        version_path.mkdir(parents=True, exist_ok=False)

    def upload_file(self, version_id: Union[str, type(...)], filename: str, file_obj: IO[bytes]) -> None:
        target_path = self._path_for_file(version_id, filename)
        _logger.debug("Adding file %s", target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._changed = True
        with open(target_path, "wb") as target_file:
            while bytes_read := file_obj.read(102400):
                target_file.write(bytes_read)

    def close(self, success: bool = False) -> None:
        if self._changed:
            for file_name, content in shared_implementations.generate_meta_data(self._deployment_spec).items():
                with open(self._path_for_file(..., file_name), "wb") as file:
                    file.write(content)
# PosixPath('/Users/philip/Documents/Development/MkdocsDeploy/private/var/folders/nb/9f9993hs2yg3gjs966_ltd8c0000gn/T/pytest-of-philip/pytest-16/test_upload0/mock_target')
# PosixPath('/Users/philip/Documents/Development/MkdocsDeploy/private/var/folders/nb/9f9993hs2yg3gjs966_ltd8c0000gn/T/pytest-of-philip/pytest-16/test_upload0/mock_target/deployments.json')
    def iter_files(self, version_id: str) -> Iterable[str]:
        def _iter_files(file_path: Path):
            try:
                for file in file_path.iterdir():
                    if not file.is_symlink():
                        if file.is_dir():
                            yield from _iter_files(file)
                        elif file.is_file():
                            yield str(file.relative_to(version_path))
            except FileNotFoundError:
                pass

        version_path = self._path_for_file(version_id)

        return _iter_files(version_path)

    def download_file(self, version_id: Union[str, type(...)], filename: str) -> IO[bytes]:
        return open(self._path_for_file(version_id, filename), "rb")

    def delete_file(self, version_id: Union[str, type(...)], filename: str) -> None:
        file_to_delete = self._path_for_file(version_id, filename)
        _logger.debug("unlink %s", file_to_delete)
        file_to_delete.unlink(missing_ok=True)
        self._changed = True
        file_to_delete = file_to_delete.parent
        # Remove any empty directories this leaves
        while file_to_delete != self._target_path:
            if next(file_to_delete.iterdir(), None) is None:
                _logger.debug("%s is empty, removing", file_to_delete)
                file_to_delete.rmdir()
                file_to_delete = file_to_delete.parent
            else:
                break

    def set_alias(self, alias_id: Union[str, type(...)], alias: Optional[DeploymentAlias]) -> None:
        if alias_id is ...:
            self._deployment_spec.default_version = alias
        else:
            if alias is None:
                try:
                    del self._deployment_spec.aliases[alias_id]
                    _recursive_delete(self._target_path / alias_id)
                except KeyError:
                    pass
            else:
                self._deployment_spec.aliases[alias_id] = alias
        self._changed = True

    @property
    def available_redirect_mechanisms(self) -> dict[str, abstract.RedirectMechanism]:
        return LOCAL_FILE_REDIRECT_MECHANISMS.copy()


    @property
    def deployment_spec(self) -> DeploymentSpec:
        return deepcopy(self._deployment_spec)

    def delete_version(self, version_id: str) -> None:
        self._check_version_exists(version_id)
        for alias_id, alias in self._deployment_spec.aliases.items():
            if alias.version_id == version_id:
                raise ValueError(f"Cannot delete a version while there are still aliases for it.  "
                                 f"Delete alias '{alias_id}' firs for version {version_id}")
        _recursive_delete(self._path_for_file(version_id))
        del self._deployment_spec.versions[version_id]
        self._changed = True

    def _path_for_file(self, version_id: Union[str, type(...)], filename: str = "") -> Path:
        if "\\" in filename:
            raise ValueError("Cannot accept filenames containing \\")
        if version_id is ...:
            if "/" in filename:
                raise ValueError(f"filename cannot contain '/' if version_id is ...: {filename}")
            return self._target_path / filename
        elif version_id not in self._deployment_spec.versions and version_id not in self._deployment_spec.aliases:
            raise abstract.VersionNotFound(version_id)
        result = Path(self._target_path, *filename.split("/"))
        # Raise a ValueError if the result is above the base path
        result.relative_to(self._target_path)
        return result

    def _check_version_exists(self, version_id: Union[str, type(...)]) -> None:
        if version_id is ...:
            return
        if version_id not in self._deployment_spec.versions:
            raise abstract.VersionNotFound(version_id)


class LocalFileTreeTarget(abstract.Target):

    def __init__(self, target_path: str):
        self._target_path = _path_from_url(target_path)

    def start_session(self) -> abstract.TargetSession:
        return LocalFileTreeTargetSession(self._target_path)


def _recursive_delete(dir_path: Path):
    if dir_path.is_dir() and not dir_path.is_symlink():
        for child in dir_path.iterdir():
            if child.is_symlink() or not child.is_dir():
                child.unlink()
            else:
                _recursive_delete(child)
        dir_path.rmdir()
    else:
        try:
            dir_path.unlink()
        except FileNotFoundError:
            pass
