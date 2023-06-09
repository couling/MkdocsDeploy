# mkdocs-deploy

## About

mkdocs-deploy began as a drop-in replacement for [mike][mike].  The main goal is to provide
a deployment tool that is version aware and plugable, capable of deploying multiple versions side by side to any target
website.

## Basic Usage (Getting Started)

Start by [configuring your project](configuration)

Build your project with mkdocs.

```shell
mkdocs build
```

To deploy this site somewhere (let's say version `1.0` will live locally at `/media/my_site/all_versions/1.0`):

```shell
mkdocs-deploy deploy 1.0
```

You can give each version a name that might appear in your theme:
```shell
mkdocs-deploy deploy 1.0 "First Version"
```

You can add extra aliases. Eg: make `1.x` forward to `1.0`.  Aliases can always be set to something different.

```shell
mkdocs-deploy set-alias 1.0 1.x
```

Aliases can be set implicitly every time you deploy a new version.  Unless otherwise configured every deployment 
implicitly replaces the `latest` alias.

## Setting up a new project

[Configure mkdocs-deploy in your project](configuration). Then...

```shell
# Deploy your first version
mkdocs-deploy deploy "1.0"

# If make sure you have at least one "latest".
mkdocs-deploy set-alias 1.0 latest 

# Set the default version for your site. Setting it to alias means it will change when latest changes
mkdocs-deploy set-
```
- Deploy your first version.
- Set a `latest` version
- Set a default version, in most cases this should be `latest`

## Built in support for

#### Source for site versions

 - Reading sites from local filesystem: as zip, tar, or directory of files.

#### Target to maintain site

 - Site on Local file system
 - [S3 Static site][aws s3 site]

#### Redirect mechanisms

 - HTML file redirects
 - S3 redirects

## Making your site Version aware.

### Through mike compatibility

The [Material](https://squidfunk.github.io/mkdocs-material/) is compatible with versioning by `mkdocs-deploy`

To enable your [material][material] themed mkdocs to understand mkdocs-deploy versioning add the following section to 
your `mkdocs.yaml` file.

```yaml
extra:
  version:
    provider: mike
```

Mkdocs-deploy generates a mike compatible file which themese can use named `versions.json`.  Looking something like this:

```json
[
   {
      "version_id": "1.0", 
      "title": "1.0", 
      "aliases": ["latest"]
   }
]
```

### Making your own theme mkdocs-deploy aware

You can either use the [mike formatted versions.json](https://github.com/jimporter/mike#for-theme-authors) or you can 
use mkdocs-deploy formatted deployments.json:

```json
{
   "versions": {
      "1.0": {
         "title": "First Release"
      }
   }, 
   "aliases": {
      "latest": {
         "version_id": "1.0", 
         "redirect_mechanisms": ["html"]
      }
   }
}
```

Note that this may be extended in future but mkdocks-deploy will endevour to ensure at least these keys are present.
The `redirect_mechanisms` available will depend on plugins installed and proboally should be ignored by theme
developers.


## If mike exists, why mkdocs-deploy?

[mike] is very good if you are looking for a simple too for deploying multiple versions of docs to github pages
from the command line.

mkdocs-deploy was designed to fill in a few places where mike is weaker:
 - Easier to work with best-practice CI pipeline
   - Does not require working on two branches at the same time
   - Separates build from deployment / publishing
 - Better suited to maintaining sites other than Github Pages
 - _(Future enhancement)_ Better suited to gitops
 - Plugable designed to allow better integration with other tools

[mike]: https://github.com/jimporter/mike "Manage multiple versions of your MkDocs-powered documentation via Git"
[aws s3 site]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html "Hosting a static website using Amazon S3"
[material]: https://squidfunk.github.io/mkdocs-material/ "Mkdocs theme named 'material'"
