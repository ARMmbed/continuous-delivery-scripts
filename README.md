<!--
Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->
# Automation Scripts for CI/CD

![Package](https://badgen.net/badge/Package/continuous-delivery-scripts/grey)
[![Documentation](https://badgen.net/badge/Documentation/GitHub%20Pages/blue?icon=github)](https://armmbed.github.io/continuous-delivery-scripts)
[![PyPI](https://badgen.net/pypi/v/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![PyPI - Status](https://img.shields.io/pypi/status/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![Downloads](https://pepy.tech/badge/continuous-delivery-scripts)](https://pepy.tech/project/continuous-delivery-scripts)

[![License](https://badgen.net/pypi/license/continuous-delivery-scripts)](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/LICENSE)
[![Compliance](https://badgen.net/badge/License%20Report/compliant/green?icon=libraries)](https://armmbed.github.io/continuous-delivery-scripts/third_party_IP_report.html)

[![Build Status](https://github.com/ARMmbed/continuous-delivery-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/ARMmbed/continuous-delivery-scripts/actions/workflows/ci.yml)

## Overview

Originally forked from [ARMmbed/mbed-tools-ci-scripts](https://github.com/ARMmbed/mbed-tools-ci-scripts), this project supports delivery workflows for projects written in different languages through [plugins](./continuous_delivery_scripts/plugins).

The scripts provide automated release flows (changelog generation, Git tags and
versioning), third-party IP auditing and reporting, and secret-registry checks.
They are designed to run in any CI system that can check out the project's Git
repository and install the required Python tools. The same project configuration
and commands can be used locally or in different CI systems, regardless of the
project's language (through its plugin). This avoids tying delivery workflows
to one CI infrastructure: a team can choose the most appropriate CI system
later, rather than having one imposed by the tooling.

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

## Usage and documentation

Code documentation is available for the most recent
production release here:

- [GitHub Pages](https://armmbed.github.io/continuous-delivery-scripts)

Following the [Unix tools philosophy](https://tldp.org/LDP/GNU-Linux-Tools-Summary/html/c1089.htm),
the package installs focused command-line tools. Run them within a project
configured by `pyproject.toml`, such as [this project](./pyproject.toml). Use
`<command> --help` for all available options; release types are `development`,
`beta` and `release`. The final column shows where each command is most likely
to be used; developer checks can also be incorporated into CI. These are the
same commands whichever CI system the team chooses.

| Command | What it does | Key arguments | Typical environment |
| --- | --- | --- | --- |
| `cd-assert-news` | Validates a branch's news files; can add a missing file for a configured dependency-update branch. | `--current-branch` (`-b`), `--local` (`-l`) | CI; `--local` for developer checks |
| `cd-create-news-file` | Creates a one-line news fragment in the configured news directory. | Required news text; `--type` (`-t`), `--ref-number` (`-n`) | Developer |
| `cd-determine-version` | Calculates and prints the **project's prospective release version** without generating a changelog. | Required `--release-type` (`-t`) | Developer preview or CI |
| `cd-generate-news` | Updates the project version and, for beta or production releases, builds the changelog from news fragments; prints the resulting version. | Required `--release-type` (`-t`) | CI release flow |
| `cd-get-config` | Prints a project configuration value. | Either `--key` (`-k`) or `--config-variable` (`-c`) | Developer or CI |
| `cd-tag-and-release` | Runs the release flow, including documentation, licensing summaries, Git tagging, packaging and publication through the selected [language plugin](./continuous_delivery_scripts/plugins). | Required `--release-type` (`-t`); optional `--current-branch` (`-b`) | CI release flow |
| `cd-generate-docs` | Generates code documentation in the configured output directory (or one specified on the command line). | `--output_directory` | Developer preview or CI |
| `cd-generate-spdx` | Generates SPDX documents and third-party licence summaries, then checks licence compliance when project metadata is available. | Required `--output-dir` (`-o`); create the directory first | CI audit; developer review also possible |
| `cd-license-files` | Adds or updates source-file licence and copyright headers when the language plugin supports them. | `--verbose` (`-v`) | Developer or CI |
| `cd-record-secrets` | Records accepted findings in the project's [detect-secrets](https://github.com/Yelp/detect-secrets) registry. | `--registry-file` (`-r`); defaults to the configured registry | Developer (registry maintenance) |
| `cd-detect-secrets` | Checks Git-tracked files against that registry and fails if new secrets are found. | `--registry-file` (`-r`); defaults to the configured registry | CI; developer checks also possible |

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
- `docs/` - Interface definition and usage documentation.
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
