from io import BytesIO

from ..abstract import DEFAULT_VERSION, RedirectMechanism, TargetSession, Version, register_shared_redirect_mechanism
from ..shared_implementations import relative_link

def enable_plugin() -> None:
    """Enables the plugin.

    Registers HTML redirect mechanism"""
    register_shared_redirect_mechanism("html", HtmlRedirect())


class HtmlRedirect(RedirectMechanism):

    def create_redirect(self, session: TargetSession, alias: Version, version_id: str) -> None:
        if alias is DEFAULT_VERSION:
            url = relative_link(target_version=version_id, target_file_name="index.html", from_root=True)
            session.upload_file(
                version_id=DEFAULT_VERSION,
                filename="index.html",
                file_obj=BytesIO(_HTML_REDIRECT_PATTERN.format(url=url).encode("utf-8"))
            )
        else:
            files_created = {
                filename for filename in session.iter_files(version_id)
                if filename.endswith(".html") or filename.endswith(".htm")
            }
            files_deleted = {
                filename for filename in session.iter_files(alias)
                if filename not in files_created and (filename.endswith("html") or filename.endswith("htm"))
            }
            for filename in files_created:
                # I really don't remember why I added this?!
                if filename == "404.html" or filename.endswith("/404.htm"):
                    session.upload_file(
                        version_id=alias,
                        filename=filename,
                        file_obj=session.download_file(version_id=version_id, filename=filename)
                    )
                else:
                    url = relative_link(target_version=version_id, target_file_name=filename)
                    session.upload_file(
                        version_id=alias, # Yes that's correct!
                        filename=filename,
                        file_obj=BytesIO(_HTML_REDIRECT_PATTERN.format(url=url).encode("utf-8"))
                    )

            for filename in files_deleted:
                session.delete_file(alias, filename)

    def refresh_redirect(self, session: TargetSession, alias: Version, version_id: str) -> None:
        # create_redirect already cleans up so no need to explicitly delete the old one
        self.create_redirect(session, alias, version_id)

    def delete_redirect(self, session: TargetSession, alias: Version) -> None:
        if alias is DEFAULT_VERSION:
            if "index.html" in session.iter_files(DEFAULT_VERSION):
                session.delete_file(version_id=DEFAULT_VERSION, filename="index.html")
        else:
            to_delete = list(session.iter_files(version_id=alias))
            for filename in to_delete:
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
