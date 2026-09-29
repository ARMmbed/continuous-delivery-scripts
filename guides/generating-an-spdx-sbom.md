# Generate an SPDX SBOM for a software project

## Problem and when to use it

Use `cd-generate-spdx` when you need SPDX tag-value documents describing the
project and its third-party dependencies, for example as an input to an
OpenChain or licence-compliance process. The tool also creates licence reports;
see [TPIP reporting](third-party-ip-reporting.md).

## Inputs and example

Install the project and its dependencies in the environment being audited.
Configure `pyproject.toml` with `PROJECT_ROOT`, `SOURCE_DIR`,
`PROGRAMMING_LANGUAGE`, your licence policy and any values required by the
selected language plugin (for example, `PACKAGE_NAME` for Python). Provide
`PROJECT_UUID` and an `[spdx]` section for the document namespace; see
[SPDX document identity](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/DEVELOPMENT.md#spdx-document-identity).
Then provide an **existing** output directory:

```bash
mkdir -p spdx-output
cd-generate-spdx --output-dir spdx-output
```

The selected language plugin must return project metadata; if it does not,
the command returns without a report. Check the installed version's
`can_get_project_metadata()` implementation; see [the Python reporting work](https://github.com/ARMmbed/continuous-delivery-scripts/pull/166)
for the status of Python metadata support.
SPDX tag-value generation also requires an SDK compatible with this project's
writer. Check the output files before treating an audit as complete. Installed
packages and platform-specific dependency markers determine what is covered;
a Linux run does not audit Windows- or macOS-only dependencies.

## Output

The directory contains a `.spdx` document for the project and each discovered
dependency, plus `third_party_IP_report.html`, `.csv` and `.txt` summaries
when metadata reporting is available. Documents are separate tag-value files,
not a single merged dependency graph.

## GitHub Actions example

After checking out the project and installing its dependencies:

```yaml
- run: mkdir -p spdx-output && cd-generate-spdx --output-dir spdx-output
- uses: actions/upload-artifact@v4
  with:
    name: spdx-report
    path: spdx-output/
```

See [`cd-generate-spdx`'s API](https://armmbed.github.io/continuous-delivery-scripts/report_third_party_ip.html)
and the [plugin guides](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
for language-specific metadata support and requirements.
