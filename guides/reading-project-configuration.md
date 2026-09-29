# Read project configuration in scripts and CI

## Problem and when to use it

Workflows and command-line scripts often need project names, paths or release
settings from `pyproject.toml`. Parsing the file in each script adds duplicate
logic and makes workflows harder to write and maintain. Use `cd-get-config` to
retrieve the same resolved values the other delivery commands use, without
writing TOML-parsing code or copying project paths into CI YAML. This makes it
easier to compose workflows and CLI commands around one project definition.

`[ProjectConfig]` is the shared delivery definition across languages: it sets
paths, versioning rules and `PROGRAMMING_LANGUAGE`. The selected plugin can
additionally use the ecosystem's native manifests and tools; see the
[plugin guides](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins).

## Inputs and example

Choose a known configuration key with `--key`, or a custom string value with
`--config-variable`:

```bash
cd-get-config --key NEWS_DIR
cd-get-config --config-variable PROJECT_NAME
NEWS_DIR="$(cd-get-config --key NEWS_DIR)"
```

Run within a project with `[ProjectConfig]` in `pyproject.toml`.
The [project configuration guide](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/DEVELOPMENT.md#project-configuration)
lists the fields needed by each workflow.

## Output

The resolved value is printed to standard output. Missing keys produce a
failing exit status. See the [sample configuration](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/pyproject.toml)
for the values used by this project.

## GitHub Actions example

After checkout and installation:

```yaml
- run: echo "News fragments live in $(cd-get-config --key NEWS_DIR)"
```

Related command: [`cd-generate-docs`](generating-code-documentation.md).
