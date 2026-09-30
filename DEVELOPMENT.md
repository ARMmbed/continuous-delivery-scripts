<!--
Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->
# Development and Testing

For development and testing purposes, it is essential to use a virtual environment. It is recommended that `pipenv` is used.

## Setup Pipenv

To start developing, install pip and pipenv on your system. Note the latter is done at user level to keep the system installation of python clean which is important on a Mac (at least):

```bash
sudo easy_install pip
```

Install pipenv (the --user is important, do not use `sudo`)

```bash
pip install --user pipenv
```

Check that pipenv is in the binary path

```bash
pipenv --version
```

If not, find the user base binary directory

```bash
python -m site --user-base
#~ /Users/<username>/Library/Python/3.7
```

Append `bin` to the directory returned and add this to your path by updating `~/.profile`. For example you might add the following:

```bash
export PATH=~/Library/Python/3.7/bin/:$PATH
```

## Setup Development Environment

Clone GitHub repository

```bash
git clone git@github.com:ARMmbed/continuous-delivery-scripts.git
```

Setup Pipenv to use Python 3 (Python 2 is not supported) and install package development dependencies:

```bash
cd continuous-delivery-scripts/
pipenv install --dev
```

## Project configuration

Each project using these commands defines its shared delivery settings under
`[ProjectConfig]` in a repository-root `pyproject.toml`. All commands read this
configuration regardless of the chosen language plugin or CI system. Start
with [this repository's configuration](./pyproject.toml), replacing paths and
names with those of your own project. The following values are needed by the
corresponding workflows; you only need to configure workflows you use.

| Setting | Needed for |
| --- | --- |
| `PROJECT_ROOT` | Locating the Git checkout and resolving project paths. Usually `"."` when `pyproject.toml` is at the repository root. |
| `PROJECT_NAME` | Naming the project in source-licence headers and the documentation landing page. |
| `PROGRAMMING_LANGUAGE` | Selecting the plugin that provides language-specific build, documentation and release operations (for example, `"Python"` or `"Golang"`). |
| `MASTER_BRANCH` | Comparing pull-request branches with the main development branch; set this explicitly if your branch is `main` rather than the built-in `master` default. |
| `NEWS_DIR` | Creating and checking news fragments and triggering changelog updates. |
| `VERSION_FILE_PATH`, `CHANGELOG_FILE_PATH` | Updating version and release-note files during a release. Also configure `[AutoVersionConfig]` and `[tool.towncrier]` for version and changelog generation. |
| `SOURCE_DIR` | Locating source files for plugins and SPDX file scanning where supported. |
| `PACKAGE_NAME` | Identifying the installed distribution for the Python metadata fetcher when SPDX reporting is supported. |
| `PROJECT_UUID` | Identifying the project's package within generated SPDX documents; also define the separate `[spdx]` namespace settings below. |
| `MODULE_TO_DOCUMENT`, `DOCUMENTATION_DEFAULT_OUTPUT_PATH`, `DOCUMENTATION_PRODUCTION_OUTPUT_PATH` | Generating a local documentation preview and publishing release documentation. The meaning of the module depends on the plugin. |
| `DOCUMENTATION_GUIDES_DIR`, `DOCUMENTATION_GUIDES_OUTPUT_FOLDER` | Optional Markdown guide source and its relative output folder; add an `index.md` in the source directory to publish guides with the API documentation. |
| `ORGANISATION`, `COPYRIGHT_START_DATE`, `FILE_LICENCE_IDENTIFIER` | Creating source copyright and licence headers. Replace the built-in organisation default for your project. |
| `ACCEPTED_THIRD_PARTY_LICENCES`, `PACKAGES_WITH_CHECKED_LICENCE` | Adjusting the accepted-licence policy and recording reviewed dependency licences where reporting is supported. |
| `GENERATE_LICENSING_SUMMARY_ON_RELEASE` | Opting into third-party licence summaries during release after documentation generation. Defaults to `false`; this repository sets it to `true`. |

Settings such as `DEPENDENCY_UPDATE_BRANCH_PATTERN` and
`AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE` can be overridden to control
automatically generated news fragments; see the
[news-checking guide](./guides/checking-news-fragments.md). The configuration
file is shared, but plugins may also read their ecosystem's native manifests
and use specialised tools, such as GoReleaser for Go. See the
[plugin guides](./continuous_delivery_scripts/plugins) for their requirements.
Provide tokens and publication credentials through your CI environment or
secret store, rather than committing them to `pyproject.toml`.

### SPDX document identity

For a plugin that supports SPDX reporting, define `PROJECT_UUID` under
`[ProjectConfig]` **and** the `[spdx]` section in the same `pyproject.toml`.
The former identifies the project package; `[spdx]` supplies the URL components
and a separate UUID for the document namespace. This repository uses:

```toml
[ProjectConfig]
PROJECT_UUID = "f0cfd7a4-30b4-11eb-adc1-0242ac120002"

[spdx]
CreatorWebsite = "spdx.org"
PathToSpdx = "spdx/spdxdocs"
UUID = "d9e2187c-30b4-11eb-adc1-0242ac120002"
```

Set values appropriate to your project rather than reusing these UUIDs. Keep
them stable across report generation so your project and SPDX document
identities remain consistent. `CreatorWebsite` and `PathToSpdx` form the
namespace URL; the SPDX generator reads `[spdx]` directly rather than through
the shared `ProjectConfig` lookup.

## Unit Tests, Code Formatting and Static Analysis

Shell into virtual environment:

```bash
pipenv shell
```

Run unit tests:

```bash
pytest
```
Note that other test runners can be used (e.g. [green](https://github.com/CleanCut/green)) 
as long as they support test written using unittest.TestCase.


Run code formatter (it will format files in place):

```bash
black .
```

Run static analysis (note that no output means all is well):

```bash
flake8
```

Perform static type check:

```bash
mypy -p continuous_delivery_scripts
```

### Testing plugins

The build matrix runs the full test suite across supported Python versions.
Dedicated CI jobs also exercise the Go and Python plugins separately.

#### Testing the Go plugin

The Go module and licence-report integration tests need the Go toolchain and
`go-licenses` binary. They are skipped locally when those tools are absent;
unit tests that mock external Go commands still run. The CI job
**test-go-plugin** sets up Go and installs `go-licenses` specifically to run
the real integration tests:

```bash
go install github.com/google/go-licenses/v2@latest
pytest -o addopts= tests/plugin/test_golang.py tests/plugin/test_go_licensing.py
```

Make sure Go's binary directory (normally `$(go env GOPATH)/bin`) is on
`PATH` so the integration test can find `go-licenses`.

#### Testing the Python plugin

The **test-python-plugin** CI job exercises Python-specific documentation,
packaging and licence-reporting tests. To run the same tests locally after
installing development dependencies:

```bash
pytest -o addopts= tests/generate_docs/test_generate_docs_python.py \
  tests/tag_and_release/test_update_documentation_python.py \
  tests/python_helpers/test_python_helpers.py \
  tests/packaging/test_package_helpers.py tests/spdx/test_python_report.py
```

## Documenting code

Inclusion of docstrings is needed in all areas of the code for Flake8 
checks in the CI to pass.

We use [google-style](http://google.github.io/styleguide/pyguide.html#381-docstrings) 
docstrings. 

To set up google-style docstring prompts in Pycharm, in the menu navigate to 
Preferences > Tools > Python Integrated Tools and in the dropdown for docstring
format select 'Google'.

For longer explanations, you can also include markdown. Markdown can also be 
kept in separate files in the `docs/user_docs` folder and included in a docstring in the 
relevant place using the [reST include](https://docutils.sourceforge.io/docs/ref/rst/directives.html#including-an-external-document-fragment) as follows:

```python
    .. include:: ../docs/user_docs/documentation.md
```

### Building docs locally

You can do a preview build of the documentation locally by running:

```bash
cd-generate-docs
```

This will generate the docs and output them to `local_docs`.
This should only be a preview. Since documentation is automatically generated 
by the CI you shouldn't commit any docs html files manually.

To add human-readable task guides, place Markdown files in the directory named
by `DOCUMENTATION_GUIDES_DIR` and link them from its `index.md`. Set
`DOCUMENTATION_GUIDES_OUTPUT_FOLDER` to the relative folder where the rendered
HTML pages should appear beneath the documentation output. Both values are
configured in `[ProjectConfig]` in `pyproject.toml`; this repository uses
`guides` for both. During documentation generation, an API index produced by a
plugin moves to `api.html`, the site index becomes a guide landing page, and a root
`llms.txt`, if present, is copied to the output. The publishing path also
works with other language plugins that generate an API index.

### Viewing docs generated by the CI

Documentation only gets committed back to this repo to the `docs`
directory during a release and this is what gets published to Github pages.
Don't modify any of the files in this directory by hand.

## Type hints

Type hints should be used in the code wherever possible. Since the 
documentation shows the function signatures with the type hints 
there is no need to include additional type information in the docstrings.

# Dependency upgrades

For dependency upgrades, dependabot is relied upon and news files are auto-generated in order to document such change. Nonetheless, due to a change in [GitHub actions](https://github.blog/changelog/2021-02-19-github-actions-workflows-triggered-by-dependabot-prs-will-run-with-read-only-permissions), secrets are not available in the build triggered by the pull request unless they are [re-run manually](https://docs.github.com/en/code-security/supply-chain-security/keeping-your-dependencies-updated-automatically/automating-dependabot-with-github-actions#manually-re-running-a-workflow). So please re-run every dependabot PR CI jobs.

# Releasing

## Third-party licence reports

The release generates HTML, CSV, text and JSON reports in `docs/`. The Python
plugin reads installed distribution metadata and packaged licence and notice
files. Run the audit in an environment containing the dependencies being
released; missing dependencies and unknown licences appear in the reports.

Set `FAIL_ON_INCOMPLETE_LICENCE_AUDIT = true` in `[ProjectConfig]` to fail
`cd-generate-spdx` and the release when a required dependency is missing or a
licence cannot be determined, unless a package has a documented manual licence
check in `PACKAGES_WITH_CHECKED_LICENCE`. The default is `false` for projects
that have not yet adopted strict auditing.

Language plugins provide package metadata through `get_current_spdx_project()`;
the shared report and policy code uses the same metadata and evidence fields
for any plugin.

## Release Types

The CI supports three release flows:

- `development` for snapshot releases
- `release` for stable releases
- `beta` for pre-releases


|   Type      |   Purpose   | Version Number Format | GitHub Release | News Files Deleted |
|-------------|-------------|-----------------------|:--------------:|:------------------:|
| Release     | General Availability | `<minor>.<major>.<patch>`                            | Yes | Yes |
| Beta        | Integration Testing  | `<minor>.<major>.<patch>-beta.<commit number>`       | Yes | No  |
| Development | Development Testing  | `<minor>.<major>.<patch>-dev+<git hash>`             | No  | No  |

> :warning: releases can be made from any branches but
> it is recommended that they are only made from the `master` branch.

### Release workflow

1. Navigate to the [GitHub Actions](https://github.com/ARMmbed/continuous-delivery-scripts/actions/workflows/release.yml) page.
2. Select the **Run Workflow** button and type which kind of release you would like to make (i.e. release, beta or development).

### Version Numbers

The version number will be automatically calculated, based on the news files.

# Detecting secrets

So that no secrets are committed back to the repository, a combination of two tools are run in CI:
- [GitLeaks]() : Scans the git history for usual secrets (e.g. AWS keys, etc.)
- [detect-secrets](https://github.com/Yelp/detect-secrets): Scans only the current state of the repository for anything which can look like secrets (strings with high entropy)

For the latter, False positive keys are stored in the [baseline](./.secrets.baseline) which `detect-secrets` checks against when it runs

## Baseline & False positives

To flag individual false positives add comment `# pragma: allowlist secret` to line with secret

To add all suspected secrets in the repository (excluding ones with an allow secret comment), run `detect-secrets scan --all-files --exclude-files 'Pipfile\.lock$' --exclude-files '.*\.html$' --exclude-files '.*\.properties$' --exclude-files 'ci.yml' --exclude-files '\.git' --exclude-files '.*_version.py' > .secrets.baseline`

If on Windows: then change the encoding of the .secrets.baseline file to UTF-8 then convert all `\` to `/` in the .secrets.baseline file
