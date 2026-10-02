<!--
Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->
# Continuous Delivery Scripts

![Package](https://badgen.net/badge/Package/continuous-delivery-scripts/grey)
[![Documentation](https://badgen.net/badge/Documentation/GitHub%20Pages/blue?icon=github)](https://armmbed.github.io/continuous-delivery-scripts)
[![PyPI](https://badgen.net/pypi/v/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![PyPI - Status](https://img.shields.io/pypi/status/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![Downloads](https://pepy.tech/badge/continuous-delivery-scripts)](https://pepy.tech/project/continuous-delivery-scripts)

[![License](https://badgen.net/pypi/license/continuous-delivery-scripts)](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/LICENSE)
[![Compliance](https://badgen.net/badge/License%20Report/compliant/green?icon=libraries)](https://armmbed.github.io/continuous-delivery-scripts/third_party_IP_report.html)

[![Build Status](https://github.com/ARMmbed/continuous-delivery-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/ARMmbed/continuous-delivery-scripts/actions/workflows/ci.yml)

## Summary

`continuous-delivery-scripts` provides Git-based CI/CD commands for release
automation, semantic versioning, changelog generation, SPDX SBOMs,
third-party IP (TPIP) and licence reports, source licence headers and secret
checks.

## Overview

Originally forked from [ARMmbed/mbed-tools-ci-scripts](https://github.com/ARMmbed/mbed-tools-ci-scripts),
the tools are written in Python but support projects in other languages through
[plugins](./continuous_delivery_scripts/plugins). Each command handles a
focused delivery task, from recording a change to auditing licences or tagging
a release. The shared project delivery definition lives in one place:
`[ProjectConfig]` in `pyproject.toml`. Every command reads those settings,
including paths, versioning rules and the selected `PROGRAMMING_LANGUAGE`,
regardless of the project's language or CI system. The selected plugin then
uses appropriate ecosystem tools: for example, GoReleaser for Go releases or
wheel and Twine for Python packages. Consult the
[plugin guides](./continuous_delivery_scripts/plugins) for language-specific
requirements; native build manifests and credentials may still be needed. See
the [project configuration guide](./DEVELOPMENT.md#project-configuration) for
the `pyproject.toml` fields required by each workflow.

Run the same commands locally or in any CI system that can check out
the project's Git repository and install the required tools. This avoids
infrastructure lock-in: the team can decide which CI system suits its project,
including after the delivery workflow has been defined.

## Usage and documentation

Start with the [common use cases](#common-use-cases) below, then follow the
[task guides](./guides/index.md) for prerequisites, outputs and CI examples.
The [GitHub Pages site](https://armmbed.github.io/continuous-delivery-scripts/)
publishes those guides alongside the API reference when release documentation
is regenerated. For individual commands and their typical developer or CI
usage, see the [command-line tools table](#command-line-tools).

To include your own Markdown guides in generated documentation, configure
their source and published folder in `[ProjectConfig]`:

```toml
DOCUMENTATION_GUIDES_DIR = "guides"
DOCUMENTATION_GUIDES_OUTPUT_FOLDER = "guides"
```

Add `guides/index.md` with links to the other `.md` files and run
`cd-generate-docs`. It renders the guides to HTML alongside the API reference;
the default published folder is `guides/`. Keep the Markdown source outside
the documentation output, which the generator clears before each build. See
[generating code documentation](./guides/generating-code-documentation.md).

## Common use cases

### Generate an SPDX SBOM and third-party IP report

For a project whose language plugin provides package metadata, generate SPDX
tag-value documents for the project and its dependencies alongside an HTML
third-party IP / TPIP licence report. Use these as inputs to an OpenChain
licence-compliance workflow:

```bash
mkdir -p spdx-output
cd-generate-spdx --output-dir spdx-output
```

The destination directory must exist. Check that your plugin supports metadata
reporting: the command can finish without producing reports when it does not.
For SPDX documents, define `PROJECT_UUID` and `[spdx]` namespace settings in
`pyproject.toml` as described under [SPDX document identity](./DEVELOPMENT.md#spdx-document-identity).
See [SPDX generation](./guides/generating-an-spdx-sbom.md) and
[TPIP reporting](./guides/third-party-ip-reporting.md) for outputs and
prerequisites.

### Automate semantic releases and changelogs

Record a change as a news fragment, then preview the next release version:

```bash
cd-create-news-file "Fix dependency resolution" --type bugfix
cd-determine-version --release-type release
```

In a configured release workflow, `cd-generate-news --release-type release`
builds the changelog from those fragments; `cd-tag-and-release` handles Git
tags and publication through the selected language plugin. See
[changelog management](./guides/managing-changelogs.md) and
[release automation](./guides/automating-releases.md).

### Manage source licence and copyright headers

Run `cd-license-files` to apply the configured source-file headers when the
language plugin supports them. See the
[licence header guide](./guides/licence-header-management.md).

### Prevent secrets from leaking through Git

Accidentally committing a password or API token can expose it to others and
leave it in repository history. Keep a reviewed detect-secrets registry and
check Git-tracked files locally or in CI before a change is merged:

```bash
cd-detect-secrets --registry-file .secrets.baseline
```

The check fails on new findings. Use `cd-record-secrets` only to record values
the team has reviewed and accepted, rather than to hide real credentials. See
[checking for secrets](./guides/checking-for-secrets.md) and
[recording accepted findings](./guides/recording-secrets.md).

## Releases

For release notes and a history of changes of all **production** releases, please see the following:

- [Changelog](./CHANGELOG.md)

For all available versions, see the:

- [PyPI Release History](https://pypi.org/project/continuous-delivery-scripts/#history)

## Versioning

The version scheme follows [PEP 440](https://peps.python.org/pep-0440/) and
[Semantic Versioning](https://semver.org/). Production releases use:

- `<major>.<minor>.<patch>`

Beta releases give early access to experimental features. They may be unstable,
and interfaces introduced in a beta release may change without notice. Beta
releases use:

- `<major>.<minor>.<patch>-beta.<pre-release-number>`

## Installation

It is recommended that a virtual environment such as [Pipenv](https://github.com/pypa/pipenv/blob/master/README.md) is
used for all installations to avoid Python dependency conflicts.

To install the most recent production quality release use:

```
pip install continuous-delivery-scripts
```

To install a specific release:

```
pip install continuous-delivery-scripts==<version>
```

## Command-line tools

Following the [Unix tools philosophy](https://tldp.org/LDP/GNU-Linux-Tools-Summary/html/c1089.htm),
the package installs focused command-line tools. Run them within a project
configured by `pyproject.toml`, such as [this project](./pyproject.toml). Use
`<command> --help` for all available options; release types are `development`,
`beta` and `release`. The final column shows where each command is most likely
to be used; developer checks can also be incorporated into CI. These are the
same commands whichever CI system the team chooses.

| Command | What it does | Key arguments | Typical environment |
| --- | --- | --- | --- |
| [`cd-assert-news`](./guides/checking-news-fragments.md) | Validates a branch's news files; can add a missing file for a configured dependency-update branch. | `--current-branch` (`-b`), `--local` (`-l`) | CI; `--local` for developer checks |
| [`cd-create-news-file`](./guides/creating-news-fragments.md) | Creates a one-line news fragment in the configured news directory. | Required news text; `--type` (`-t`), `--ref-number` (`-n`) | Developer |
| [`cd-determine-version`](./guides/previewing-versions.md) | Calculates and prints the **project's prospective release version** without generating a changelog. | Required `--release-type` (`-t`) | Developer preview or CI |
| [`cd-generate-news`](./guides/managing-changelogs.md) | Updates the project version and, for beta or production releases, builds the changelog from news fragments; prints the resulting version. | Required `--release-type` (`-t`) | CI release flow |
| [`cd-get-config`](./guides/reading-project-configuration.md) | Prints a project configuration value. | Either `--key` (`-k`) or `--config-variable` (`-c`) | Developer or CI |
| [`cd-tag-and-release`](./guides/automating-releases.md) | Runs the release flow, including documentation, licensing summaries, Git tagging, packaging and publication through the selected [language plugin](./continuous_delivery_scripts/plugins). | Required `--release-type` (`-t`); optional `--current-branch` (`-b`) | CI release flow |
| [`cd-generate-docs`](./guides/generating-code-documentation.md) | Generates code documentation in the configured output directory (or one specified on the command line). | `--output_directory` | Developer preview or CI |
| [`cd-generate-spdx`](./guides/generating-an-spdx-sbom.md) | Generates SPDX documents and third-party licence summaries, then checks licence compliance when project metadata is available. | Required `--output-dir` (`-o`); optional `--lookup-scancode`, `--skip-dependency-download` | CI audit; developer review also possible |
| [`cd-check-licence-compliance`](./guides/checking-licence-compliance.md) | Checks project and dependency licences without creating SPDX documents; optionally writes third-party IP summaries. | Optional `--output-dir` (`-o`) for reports, `--lookup-scancode`, `--skip-dependency-download` | CI gate or developer review |
| [`cd-license-files`](./guides/licence-header-management.md) | Adds or updates source-file licence and copyright headers when the language plugin supports them. | `--verbose` (`-v`) | Developer or CI |
| [`cd-record-secrets`](./guides/recording-secrets.md) | Records accepted findings in the project's [detect-secrets](https://github.com/Yelp/detect-secrets) registry. | `--registry-file` (`-r`); defaults to the configured registry | Developer (registry maintenance) |
| [`cd-detect-secrets`](./guides/checking-for-secrets.md) | Checks Git-tracked files against that registry and fails if new secrets are found. | `--registry-file` (`-r`); defaults to the configured registry | CI; developer checks also possible |

For example, `cd-create-news-file "Fix dependency resolution" --type bugfix`
adds a news fragment. For release workflow details, see the
[development guide](./DEVELOPMENT.md).

For GitHub automation that performs authenticated clone or fetch operations, see [GitHub Token Authentication](#github-token-authentication).

## GitHub Token Authentication

When git operations need to retry against GitHub over HTTPS, this project now uses the credential layout `https://x-access-token:<token>@github.com/<owner>/<repo>.git`.

This means the token is sent in the password position with `x-access-token` as the username, which is the format GitHub accepts for workflow-generated and other non-OAuth tokens used by automation.

Older `https://<token>:x-oauth-basic@github.com/...` URLs were tied to OAuth-style credentials and could reject tokens created dynamically during CI/CD flows.

## Project Structure

The main parts of the repository are:

- `.github` - CI and GitHub configuration files.
- `docs/` - Generated GitHub Pages guides and API reference (rebuilt on release).
- `guides/` - Markdown source for task-based documentation.
- `llms.txt` - A concise map of the published documentation.
- `continuous_delivery_scripts/` - Python source files and language plugins.
- `news/` - Collection of news files for unreleased changes.
- `tests/` - Unit and integration tests.

## Getting Help

- For interface definition and usage documentation, please see [GitHub Pages](https://armmbed.github.io/continuous-delivery-scripts).
- For a list of known issues and possible workarounds, please see [Known Issues](./KNOWN_ISSUES.md).
- To raise a defect or enhancement please use [GitHub Issues](https://github.com/ARMmbed/continuous-delivery-scripts/issues).

## Contributing

- We are committed to fostering a welcoming community, please see our
  [Code of Conduct](./CODE_OF_CONDUCT.md) for more information.
- For ways to contribute to the project, please see the [Contributions Guidelines](./CONTRIBUTING.md)
- For a technical introduction into developing this package, please see the [Development Guide](./DEVELOPMENT.md)
