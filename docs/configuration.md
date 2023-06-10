# Configuration

## Where

When you use the `mkdocs-deploy` it will, by default, search for a configuration file starting with the current 
directory and working up though the parents.  If you specify `--config-file` then it will not search and will just 
attempt to use that file.

It supports three different files:
 - `mkdocs-deploy.yaml` Settings in YAML
 - `mkdocs-deploy.json` Settings in json
 - `pyproject.toml` Settings in the section `[tool.mkdocs-deploy]`

Sadly `mkdocs_config.yaml` is not currently supported as this can't yet be done without mkdocs trying to validate 
mkdocs-deploy settings.

## Overrides

Some settings can be overriden at runtime for convenience.  This means that you don't necessarily need to configure a
project at all.  However, there is no plan to expose all settings.

## Settings

| Setting                | Override option        | Description                                                                                                                                                                                                                |
|------------------------|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `built_site`           | `--built-site`         | The file path or URL to locate the output from mkdocs known in mkdocs as [site_dir](https://www.mkdocs.org/user-guide/configuration/#site_dir).  This may a directory, tar file, zip file, or URL for a plugin to fetch.   |
| `build_site_pattern`   | `--built-site-pattern` | Override `built_site` with a [glob pattern](https://en.wikipedia.org/wiki/Glob_(programming)). This pattern will be used to search for the built_site.  The first matching file or directory will be used.                 |
| `deploy_url`           | `--deploy-url`         | The local file or remote URL to publish to.  This is always the base, not the individual version address                                                                                                                   |
| `default_aliases`      |                        | A coma seperated list of aliases to add when deploying by default. Defaults to `latest`. This means by default the most recent deployment will always be marked as the latest.                                             |
| `redirect_mechanisms`  |                        | Redirecting browsers from an alias to it's version can be done in a large number of ways, mny dependent on the specific webserver.  This coma seperated string let's you decide which mechanism[s] to use. Default `html`  |

## Examples

### Simple `mkdocs-deploy.yaml`

```yaml
built_site: site
# Eg for a linux webserver
deploy_url: /var/www/html
```

### Simple mkdocs-deploy.json publishing to s3

Here the bucket name is `example.com`.

```json
{
  "built_site": "site",
  "deploy_url": "s3://example.com/"
}
```

### pyproject.toml where the source is a versioned zip file
```toml
[tool.mkdocs-deploy]
built_site_pattern = "dist/site-name-*.zip"
deploy_url = "/var/www/html"
```