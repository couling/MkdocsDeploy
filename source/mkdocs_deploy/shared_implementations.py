from io import BytesIO

from .abstract import RedirectMechanism, TargetSession
from .versions import DeploymentSpec


def generate_meta_data(deployment_spec: DeploymentSpec) -> dict[str, bytes]:
    """
    Generate metadata files to write at the root of a site.

    This just creates a dict with the filenames and content to write to them as bytes.
    At present this is just deployments.json and versions.json.  More may be added in the future.
    :param deployment_spec: The deployment spec to covert to files.
    :return: A dictionary with filenames as keys and the bytes to write to them
    """
    return {
        "deployments.json": deployment_spec.json().encode("utf-8"),
        "versions.json": deployment_spec.mike_versions().json().encode("utf-8"),
    }

class HtmlRedirect(RedirectMechanism):

    def create_redirect(self, session: TargetSession, alias: str, version_id: str) -> None:
        files_created = set()
        for filename in session.iter_files(version_id):
            if filename.endswith(".html") or filename.endswith(".htm"):
                if filename == "404.html" or filename.endswith("/404.html"):
                    session.upload_file(
                        version_id=alias,
                        filename=filename,
                        file_obj=session.download_file(version_id=version_id, filename=filename)
                    )
                else:
                    url = filename
                    depth = len(url.split("/"))
                    url = ("../" * depth + version_id + "/" + url)
                    session.upload_file(
                        version_id=alias, # Yes that's correct!
                        filename=filename,
                        file_obj=BytesIO(_HTML_REDIRECT_PATTERN.format(url=url).encode("utf-8"))
                    )
                files_created.add(filename)
        for filename in session.iter_files(alias):
            if filename not in files_created and (filename.endswith("html") or filename.endswith("htm")):
                session.delete_file(alias, filename)

    def delete_redirect(self, session: TargetSession, alias: str) -> None:
        for filename in session.iter_files(alias):
            if filename.endswith("html") or filename.endswith("htm"):
                session.delete_file(version_id=alias, filename=filename)

_HTML_REDIRECT_PATTERN="""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Redirecting</title>
  <noscript>
    <meta http-equiv="refresh" content="1; url={url}" />
  </noscript>
  <script>
    window.location.replace("{url}" + window.location.hash);
  </script>
</head>
<body>
  Redirecting to <a href="{url}">{url}</a>...
</body>
</html>
"""

SHARED_REDIRECT_MECHANISMS = {
    'html': HtmlRedirect()
}