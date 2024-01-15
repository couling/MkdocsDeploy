import io
from copy import deepcopy
from io import BytesIO
from typing import IO, Iterable

from mkdocs_deploy import abstract, versions
from mkdocs_deploy.abstract import TargetSession, Version
from mkdocs_deploy.versions import DeploymentAlias, DeploymentSpec


class BaseMockPlugin:

    files: dict[str, bytes]

    def __init__(self):
        self.files = {}


class MockSource(abstract.Source):

    def __init__(self, files: dict[str, bytes] | None = None):
        self.files = files.copy() if files is not None else {}

    def iter_files(self) -> Iterable[str]:
        yield from self.files.keys()

    def open_file_for_read(self, filename: str) -> IO[bytes]:
        return io.BytesIO(initial_bytes=self.files[filename])


class MockRedirectMechanism(abstract.RedirectMechanism):

    def create_redirect(self, session: TargetSession, alias: Version, version_id: str) -> None:
        pass

    def delete_redirect(self, session: TargetSession, alias: Version) -> None:
        pass


class MockTargetSession(abstract.TargetSession):
    files: dict[tuple[Version, str], bytes]
    internal_deployment_spec: abstract.DeploymentSpec
    closed: bool = False
    close_success: bool = False
    aliases: dict[Version, versions.DeploymentAlias]
    redirect_mechanisms: dict[str, abstract.RedirectMechanism] = {'mock': MockRedirectMechanism()}

    def __init__(self):
        self.files = {}
        self.deleted_files = set()
        self.internal_deployment_spec = abstract.DeploymentSpec()
        self.aliases = {}
        self.redirect_mechanisms = self.redirect_mechanisms.copy()

    def start_version(self, version_id: str, title: str) -> None:
        self.internal_deployment_spec.versions[version_id] = versions.DeploymentVersion(title=title)

    def delete_version(self, version_id: str) -> None:
        existing_files = [f for v, f in self.files.keys() if v == version_id]
        del self.internal_deployment_spec.versions[version_id]
        for file in existing_files:
            del self.files[(version_id, file)]

    def upload_file(self, version_id: Version, filename: str, file_obj: IO[bytes]) -> None:
        if version_id not in self.internal_deployment_spec.versions:
            raise abstract.VersionNotFound(version_id)
        self.files[(version_id, filename)] = file_obj.read()

    def download_file(self, version_id: Version, filename: str) -> IO[bytes]:
        if version_id not in self.internal_deployment_spec.versions:
            raise abstract.VersionNotFound(version_id)
        return BytesIO(self.files[(version_id, filename)])

    def delete_file(self, version_id: Version, filename: str) -> None:
        if version_id not in self.internal_deployment_spec.versions:
            raise abstract.VersionNotFound(version_id)
        del self.files[(version_id, filename)]

    def iter_files(self, version_id: str) -> Iterable[str]:
        for version, file in self.files:
            if version_id == version:
                yield file

    def close(self, success: bool = False) -> None:
        self.closed = True
        self.close_success = success

    def set_alias(self, alias_id: Version, alias: DeploymentAlias | None) -> None:
        if alias is None:
            del self.aliases[alias_id]
            return
        self.aliases[alias_id] = deepcopy(alias)
        if alias_id is abstract.DEFAULT_VERSION:
            self.internal_deployment_spec.default_version = self.aliases[alias_id]
        else:
            self.internal_deployment_spec.aliases[alias_id] = self.aliases[alias_id]

    @property
    def available_redirect_mechanisms(self) -> dict[str, abstract.RedirectMechanism]:
        return self.redirect_mechanisms

    @property
    def deployment_spec(self) -> DeploymentSpec:
        return deepcopy(self.internal_deployment_spec)


class MockTarget(abstract.Target):

    files: dict[tuple[str, str], bytes]
    internal_deployment_spec: versions.DeploymentSpec

    def __init__(self):
        self.files = {}
        self.internal_deployment_spec = versions.DeploymentSpec()

    def start_session(self) -> MockTargetSession:
        return MockTargetSession()
