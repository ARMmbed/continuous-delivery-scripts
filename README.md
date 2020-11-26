# Automation Scripts for CI/CD

![Package](https://badgen.net/badge/Package/continuous-delivery-scripts/grey)
[![Documentation](https://badgen.net/badge/Documentation/GitHub%20Pages/blue?icon=github)](https://armmbed.github.io/continuous-delivery-scripts)
[![PyPI](https://badgen.net/pypi/v/continuous-delivery-scripts)](https://pypi.org/projectcontinuous-delivery-scripts/)
[![PyPI - Status](https://img.shields.io/pypi/status/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/continuous-delivery-scripts)](https://pypi.org/project/continuous-delivery-scripts/)

[![License](https://badgen.net/pypi/license/continuous-delivery-scripts)](https://github.com/ARMmbed/continuous-delivery-scripts/blob/master/LICENSE)
[![Compliance](https://badgen.net/badge/License%20Report/compliant/green?icon=libraries)](https://armmbed.github.io/continuous-delivery-scripts/third_party_IP_report.html)

[![Build Status](https://dev.azure.com/cmsis-tools/continuous-delivery-scripts/_apis/build/status/Build%20and%20Release?branchName=main&stageName=CI%20Checkpoint)](https://dev.azure.com/cmsis-tools/continuous-delivery-scripts/_build/latest?definitionId=8&branchName=main)
[![Test Coverage](https://codecov.io/gh/ARMmbed/continuous-delivery-scripts/branch/master/graph/badge.svg)](https://codecov.io/gh/ARMmbed/continuous-delivery-scripts)
[![Maintainability](https://api.codeclimate.com/v1/badges/41301e959f22986b7b2b/maintainability)](https://codeclimate.com/github/ARMmbed/continuous-delivery-scripts/maintainability)

## Overview

Project initially forked from ARMmbed/mbed-tools-ci-scripts but modified so that it can be used for any projects and any languages.

Continuous Delivery scripts for any projects:
- Automated release flows (i.e. changelog generation, git tags, versioning)
- third party IP auditing and reporting


## Releases

For release notes and a history of changes of all **production** releases, please see the following:

- [Changelog](https://github.com/ARMmbed/continuous-delivery-scripts/blob/master/CHANGELOG.md)

For a the list of all available versions please, please see the:

- [PyPI Release History](https://pypi.org/project/continuous-delivery-scripts/#history)

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
pip install continuous-delivery-scripts
```

To install a specific release:

```
pip install continuous-delivery-scripts==<version>
```

## Usage

Interface definition and usage documentation is available for the most recent
production release here:

- [GitHub Pages](https://armmbed.github.io/continuous-delivery-scripts)

## Project Structure

The follow described the major aspects of the project structure:

- `azure-pipelines/` - CI configuration files for Azure Pipelines.
- `docs/` - Interface definition and usage documentation.
- `examples/` - Usage examples.
- `continuous-delivery-scripts/` - Python source files.
- `news/` - Collection of news files for unreleased changes.
- `tests/` - Unit and integration tests.

## Getting Help

- For interface definition and usage documentation, please see [GitHub Pages](https://armmbed.github.io/continuous-delivery-scripts).
- For a list of known issues and possible workarounds, please see [Known Issues](KNOWN_ISSUES.md).
- To raise a defect or enhancement please use [GitHub Issues](https://github.com/ARMmbed/continuous-delivery-scripts/issues).

## Contributing

- We are committed to fostering a welcoming community, please see our
  [Code of Conduct](https://github.com/ARMmbed/continuous-delivery-scripts/blob/master/CODE_OF_CONDUCT.md) for more information.
- For ways to contribute to the project, please see the [Contributions Guidelines](https://github.com/ARMmbed/continuous-delivery-scripts/blob/master/CONTRIBUTING.md)
- For a technical introduction into developing this package, please see the [Development Guide](https://github.com/ARMmbed/continuous-delivery-scripts/blob/master/DEVELOPMENT.md)
