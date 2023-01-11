# mkdocs-deploy

## About

mkdocs-deploy began as a drop-in replacement for [mike][mike].  The main goal is to provide
a deployment tool that is version aware and plugable, capable of deploying multiple versions side by side to any target
website.

## Basic Usage (Getting Started)




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

To enable your [material][material] themed mkdocs to understand mkdocs-deploy versioning ad the following section to 
your `mkdocs.yaml` file.

```yaml
extra:
  version:
    provider: mike
```

### Making your own theme mkdocs-deploy aware

mkdocs-deploy has an additional json file describing versions.

You can make your theme aware of which versions are installed and which aliases for them.

```json
{
   "versions": {
      "1.0": {
         "title": "1.0"
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

_This may be extended in the future._


## If mike exists, why mkdocs-deploy

Mike][mike] is very good if you are looking for a simple too for deploying multiple versions of docs to github pages
from the command line.

mkdocs-deploy was designed to fill in a few places where mike is weaker:
 - Easier to work with best-practice CI pipeline
   - Does not require working on two branches at the same time
   - Separates build from deployment
 - Better suited to maintaining sites other than GithubPages
 - _(Future enhancement)_ Better suited to gitops
 - Plugable designed to allow better integration with other tools

[mike]: https://github.com/jimporter/mike "Manage multiple versions of your MkDocs-powered documentation via Git"
[aws s3 site]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html "Hosting a static website using Amazon S3"
[material]: https://squidfunk.github.io/mkdocs-material/ "Mkdocs theme named 'material'"