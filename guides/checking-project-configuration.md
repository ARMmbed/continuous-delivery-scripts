# Check CDS project configuration

## Problem and when to use it

Use `cd-check-project-config` when you want to validate the CDS-specific
`[ProjectConfig]` section in `pyproject.toml` before running other delivery
commands. It is useful when setting up a project, reviewing configuration
changes, or debugging why another CDS command fails early.

The command checks the configuration keys CDS understands, validates expected
types, verifies some formats such as regexes, URLs and UUIDs, and reuses the
existing validation for licence-assessment policy overrides.

## Inputs and example

Run the command in a repository with `pyproject.toml`:

```bash
cd-check-project-config
```

To validate a specific file path instead of the nearest project config:

```bash
cd-check-project-config --config-file path/to/pyproject.toml
```

## Output

The command prints `Project configuration is valid.` when the configuration
passes validation. It fails if CDS finds unknown `ProjectConfig` keys, invalid
types, malformed values, or invalid licence-assessment policy settings.

Use it before [`cd-check-licence-compliance`](checking-licence-compliance.md),
[`cd-generate-spdx`](generating-an-spdx-sbom.md) or
[`cd-tag-and-release`](automating-releases.md) when configuration changes are
part of the work.
