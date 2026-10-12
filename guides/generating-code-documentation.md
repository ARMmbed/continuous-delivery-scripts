# Generate code documentation for a project

## Problem and when to use it

Use `cd-generate-docs` to rebuild a project's API documentation through its
language plugin. Preview locally before committing or publishing a release.

## Inputs and example

Set `MODULE_TO_DOCUMENT`, `PROGRAMMING_LANGUAGE` and the documentation paths
in `pyproject.toml`. To publish task guides with the API pages, set the
optional `DOCUMENTATION_GUIDES_DIR` to a directory containing `index.md` and
other Markdown guides. `DOCUMENTATION_GUIDES_OUTPUT_FOLDER` selects where
rendered guides appear beneath the documentation output (default: `guides`).
If the project publishes documentation at a known public URL, set
`DOCUMENTATION_SITE_URL` to that base URL (including a project path, if any).
CDS then adds a sitemap, a permissive `robots.txt`, an `llms.txt` index and a
consolidated `llms-full.txt` of the rendered task guides when applicable.
For each file, `cd-generate-docs` first looks for an authored version in the
repository root, then `DOCUMENTATION_GUIDES_DIR`, then the directory selected
by `MODULE_TO_DOCUMENT`. It copies the first one found to the documentation
output and generates a missing file when possible. Without a
configured URL, CDS checks the Git remote for GitHub Pages and uses the site
URL only when it can verify that the website is publicly reachable. Set
`DOCUMENTATION_SITE_URL` explicitly for custom domains or offline builds.
The generated guide pages and landing page include Schema.org JSON-LD when
the URL is configured.
**GitHub Pages project sites:** If the documentation is served under
`/<repository>/`, CDS publishes `robots.txt` at
`/<repository>/robots.txt`. Search crawlers check only `/robots.txt` at the
domain root for crawl rules. The project-path file therefore cannot allow or
block crawling of the project's pages; only the owner of the domain root can
set those rules. The project's `sitemap.xml` is still accessible under its
project path and can be submitted directly to a search engine.
The default output is the configured preview directory:

```bash
cd-generate-docs
```

To choose another output directory, use `--output_directory` (with an
underscore). The tool clears the destination before generating documentation;
do not point it at a directory containing unrelated files.

## Output

Documentation in the format produced by the selected plugin. Where a plugin
generates an HTML API index, the guide landing page links to it as `api.html`.
This repository publishes task-oriented guides alongside generated documentation
when it regenerates `docs/`. See the [plugin guides](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
for language-specific documentation tooling.

## GitHub Actions example

After installing the project and its documentation dependencies:

```yaml
- run: cd-generate-docs --output_directory docs
```

Related configuration: [`cd-get-config`](reading-project-configuration.md).
