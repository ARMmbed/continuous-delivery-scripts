# Python plugin

This plugin is used for python projects when `PROGRAMMING_LANGUAGE` is set to `python`.

## Release
The plugin uses `wheel` to package the project before releasing it. 

The plugin uses twine to release packages to PYPI.
For that purpose, two environment variables need to be set:
- `TWINE_USERNAME`: the username of the PYPI account
- `TWINE_PASSWORD`: the password of the PYPI account

## Documentation
The plugin uses [pdoc](https://pdoc3.github.io/pdoc/) to generate the code reference documentation

## Third-party licence audit

The Python plugin reads metadata from the **installed** project distribution and
walks its `Requires-Dist` entries to find installed, transitive dependencies.
Install the dependencies you intend to audit, then run the audit in that
environment; the plugin does not install packages itself. This is deliberate:
Python projects can define dependencies in many different ways, so CDS cannot
reliably infer and reproduce the intended audit environment automatically.

> **Warning — platform limitation:** The audit only sees dependencies installed
> for the current platform and Python version. It does **not** inspect
> dependencies conditional on other platforms. The release CI runs on Linux,
> so a report generated there is likely to omit Windows- and macOS-only
> dependencies. Audit those platforms in their own environments if they are
> supported by the project.

The plugin supplies package metadata to the shared SPDX, policy and report
code, so other language plugins can use the same reporting pipeline.

For each distribution, the audit prefers its PEP 639 `License-Expression`, then
the legacy `License` field, then licence classifiers when they identify a
single licence. It retains all classifiers and their possible SPDX identifiers
for review rather than assuming that multiple classifiers mean a choice of
licence. It also reads packaged `License-File` entries (or common licence
filenames) and notice files as **evidence**, not as an automatically detected
licence. The project’s own source files are checked for SPDX licence and
copyright notices separately.

The release writes `third_party_IP_report.html`, `.csv`, `.txt` and `.json` to
`docs/`; `cd-generate-spdx --output-dir <directory>` also generates SPDX
documents and these summaries in the requested directory. Reports identify
the source of each licence, missing dependencies, unknown declarations and
manual-check reasons configured in `PACKAGES_WITH_CHECKED_LICENCE`. Set
`FAIL_ON_INCOMPLETE_LICENCE_AUDIT = true` in `[ProjectConfig]` to fail the
audit or release when required dependencies or usable licence declarations
are missing, or an exemption lacks a reason. This check is opt-in.

### Comparison with other Python licence tools

All three approaches read **installed distribution metadata** rather than
running `setup.py develop` to discover dependency licences:

| Tool | What differs from this plugin |
| --- | --- |
| [pip-licenses](https://github.com/raimon49/pip-licenses) | Lists packages installed in the selected environment and offers several output formats and simple licence filters. This plugin starts from the project’s dependency tree and also produces SPDX documents and checks the project’s source files. |
| [license-audit](https://github.com/dgeragh/license-audit) | Walks dependencies and tracks licence provenance, but also includes other installed packages; it adds OSADL-based compatibility analysis and outbound-licence recommendations. This plugin instead applies the project’s configured accepted-licence policy and manual checks, and records packaged licence and notice text as review evidence. |

Neither installed-metadata approach can establish the licence of bundled code
that a dependency does not declare. Review unknown results and the packaged
licence text before making a compliance decision.
