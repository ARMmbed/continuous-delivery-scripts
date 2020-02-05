# Mbed Tools CI Scripts

![Package](https://img.shields.io/badge/package-mbed--tools--ci--scripts-lightgrey)
[![Documentation](https://img.shields.io/badge/Documentation-GitHub_Pages-blue)](https://armmbed.github.io/mbed-tools-ci-scripts)
[![PyPI](https://img.shields.io/pypi/v/mbed-tools-ci-scripts)](https://pypi.org/project/mbed-tools-ci-scripts/)
[![PyPI - Status](https://img.shields.io/pypi/status/mbed-tools-ci-scripts)](https://pypi.org/project/mbed-tools-ci-scripts/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mbed-tools-ci-scripts)](https://pypi.org/project/mbed-tools-ci-scripts/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/ARMmbed/mbed-tools-ci-scripts/blob/master/LICENSE)

[![Build Status](https://dev.azure.com/mbed-tools/mbed-tools-ci-scripts/_apis/build/status/Build%20and%20Release?branchName=master)](https://dev.azure.com/mbed-tools/mbed-tools-ci/_build/latest?definitionId=3&branchName=master)
[![Test Coverage](https://codecov.io/gh/ARMmbed/mbed-tools-ci-scripts/branch/master/graph/badge.svg)](https://codecov.io/gh/ARMmbed/mbed-tools-ci-scripts)
[![Maintainability](https://api.codeclimate.com/v1/badges/41301e959f22986b7b2b/maintainability)](https://codeclimate.com/github/ARMmbed/mbed-tools-ci-scripts/maintainability)

## Overview

Continuous Integration scripts used by mbed-tools projects.


## Releases

For release notes and a history of changes of all **production** releases, please see the following:

- [Changelog](https://github.com/ARMmbed/mbed-tools-ci-scripts/blob/master/CHANGELOG.md)

For a the list of all available versions please, please see the:

- [PyPI Release History](https://pypi.org/project/mbed-tools-ci-scripts/#history)

## Versioning

The version scheme used follows [PEP440](https://www.python.org/dev/peps/pep-0440/) and 
[Semantic Versioning](https://semver.org/). For production quality releases the version will look as follows:

- `<major>.<minor>.<patch>`

Beta releases are used to give early access to new functionality, for testing and to get feedback on experimental 
features. As such these releases may not be stable and should not be used for production. Additionally any interfaces
introduced in a beta release may be removed or changed without notice. For **beta** releases the version will look as
follows:

- `<major>.<minor>.<patch>-beta.<pre-release-number>`

## Installation

It is recommended that a virtual environment such as [Pipenv](https://github.com/pypa/pipenv/blob/master/README.md) is
used for all installations to avoid Python dependency conflicts.

To install the most recent production quality release use:

```
pip install mbed-tools-ci-scripts
```

To install a specific release:

```
pip install mbed-tools-ci-scripts==<version>
```

## Usage

Interface definition and usage documentation (for developers of Mbed OS tooling) is available for the most recent
production release here:

- [GitHub Pages](https://armmbed.github.io/mbed-tools-ci-scripts)

## Project Structure

The follow described the major aspects of the project structure:

- `azure-pipelines/` - CI configuration files for Azure Pipelines.
- `docs/` - Interface definition and usage documentation.
- `examples/` - Usage examples.
- `mbed_tools_ci_scripts/` - Python source files.
- `news/` - Collection of news files for unreleased changes.
- `tests/` - Unit and integration tests.
