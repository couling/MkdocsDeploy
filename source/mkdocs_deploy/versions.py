import pydantic
from typing import Iterable, Optional

DEPLOYMENTS_FILENAME = 'deployments.json'
MIKE_VERSIONS_FILENAME = 'versions.json'


# [{"version": "2.1", "title": "2.1", "aliases": []}, {"version": "2.0", "title": "2.0", "aliases": ["latest"]}]

class MikeVersion(pydantic.BaseModel):
    version: str
    title: str = None
    aliases: list[str] = []

    @pydantic.root_validator()
    def _default_title(cls, values: dict):
        if values["title"] is None:
            values["title"] = values["version"]
        return values


class MikeVersions(pydantic.BaseModel):
    __root__: list[MikeVersion] = []


class DeploymentVersion(pydantic.BaseModel):
    title: str = None

    @pydantic.root_validator()
    def _default_title(cls, values: dict):
        if values["title"] is None:
            values["title"] = values["version_id"]
        return values


class DeploymentAlias(pydantic.BaseModel):
    version_id: str
    redirect_mechanisms: set[str]


class DeploymentSpec(pydantic.BaseModel):
    default_version: Optional[DeploymentAlias] = None
    versions: dict[str, DeploymentVersion] = {}
    aliases: dict[str, DeploymentAlias] = {}

    def mike_versions(self) -> MikeVersions:
        versions = {
            version_id: MikeVersion(version=version_id, title=version.title)
            for version_id, version in self.versions.items()
        }
        for alias_id, alias in self.aliases.items():
            versions[alias.version_id].aliases.append(alias_id)
        return MikeVersions(__root__=list(versions.values()))


    def aliases_for_version(self, version_id: str) -> Iterable[str]:
        """
        Discover all aliases for a given version
        :param version_id: the version to search for
        :return: An iterable of alias_ids for the given version
        """
        for alias_id, alias in self.aliases.items():
            if alias.version_id == version_id:
                yield alias_id
