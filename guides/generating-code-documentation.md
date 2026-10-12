# Generate code documentation for a project

## Problem and when to use it

Use `cd-generate-docs` to rebuild a project's API documentation through its
language plugin. Preview locally before committing or publishing a release.

## Inputs and example

Set `MODULE_TO_DOCUMENT`, `PROGRAMMING_LANGUAGE` and the documentation paths
in `pyproject.toml`. For Go, `MODULE_TO_DOCUMENT` names the module or package
to document; CDS derives the working directory and Go package pattern.
To publish task guides with the API pages, set the
optional `DOCUMENTATION_GUIDES_DIR` to a directory containing `index.md` and
other Markdown guides. `DOCUMENTATION_GUIDES_OUTPUT_FOLDER` selects where
rendered guides appear beneath the documentation output (default: `guides`).
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
The API pages link back to the guide index, including from nested packages.
This repository publishes task-oriented guides alongside generated documentation
when it regenerates `docs/`. See the [plugin guides](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
for language-specific documentation tooling.
See the [Golang plugin guide](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/continuous_delivery_scripts/plugins/GOLAND.MD#documentation)
for Go module and package selection without having to specify `./...`.

## GitHub Actions example

After installing the project and its documentation dependencies:

```yaml
- run: cd-generate-docs --output_directory docs
```

Related configuration: [`cd-get-config`](reading-project-configuration.md).
