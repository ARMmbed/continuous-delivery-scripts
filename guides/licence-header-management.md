# Apply copyright and source licence headers

## Problem and when to use it

Use `cd-license-files` to add or update licence and copyright notices on
project source files according to the configured organisation and language
plugin. Run it when creating files or before release so source notices remain
consistent. It is distinct from auditing the licences of *dependencies*.

## Inputs and example

Set `PROGRAMMING_LANGUAGE`, `ORGANISATION`, `COPYRIGHT_START_DATE` and the
licence identifier in `pyproject.toml`. The plugin must support source header
generation:

```bash
cd-license-files
```

Review the resulting source-file changes before committing. The command
skips a project whose language plugin does not support licence headers. See
the [plugin guides](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
for language-specific templates and support.

## Output

Source-file copyright and SPDX notices are applied or refreshed in the Git
checkout. For dependency licence reporting instead, see
[the TPIP guide](third-party-ip-reporting.md).

## GitHub Actions example

After checkout and installation:

```yaml
- run: cd-license-files
- run: git diff --check
```

Related command: [`cd-generate-spdx`](generating-an-spdx-sbom.md).
