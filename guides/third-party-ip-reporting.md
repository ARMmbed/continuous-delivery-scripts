# Generate a third-party IP (TPIP) and licence report

## Problem and when to use it

Use `cd-generate-spdx` to document dependency licences for a third-party IP
(TPIP) review and to check them against the project's accepted-licence policy.
It can support an OpenChain compliance workflow; a generated report alone does
not certify compliance. For the SPDX documents produced by the same command,
see [SPDX generation](generating-an-spdx-sbom.md).

## Inputs and example

Install the dependencies you intend to audit, configure your language plugin
and set `ACCEPTED_THIRD_PARTY_LICENCES` and any documented manual checks in
`pyproject.toml`. Choose an existing output directory:

```bash
mkdir -p licensing
cd-generate-spdx --output-dir licensing
```

The selected plugin must support metadata extraction. It uses tools suited to
the project's language to obtain dependency and licence information for the
shared report and accepted-licence policy. Check the
[plugin documentation](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
for language-specific prerequisites and support.
An audit covers the installed environment, so run it for each supported
platform if dependencies differ by operating system. Review unknown licences
and packaged notices rather than assuming a missing value means permission.

## Output

Find `third_party_IP_report.html`, `.csv`, `.json` and `.txt` in the output directory,
alongside SPDX documents when generation is enabled. In this repository the
HTML report is published to GitHub Pages after a release regenerates `docs/`.
The HTML report has download links for the accompanying CSV, JSON and text
reports when these files are kept together in the same directory.

## GitHub Actions example

Once the project and its dependencies are installed:

```yaml
- run: mkdir -p licensing && cd-generate-spdx --output-dir licensing
- uses: actions/upload-artifact@v4
  with:
    name: third-party-ip-report
    path: licensing/
```

Related commands: [`cd-check-licence-compliance`](checking-licence-compliance.md)
for reports without SPDX documents, [`cd-generate-spdx`](generating-an-spdx-sbom.md)
and [`cd-license-files`](licence-header-management.md).
