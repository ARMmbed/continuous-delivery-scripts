# Check project and dependency licence compliance

## Problem and when to use it

Use `cd-check-licence-compliance` as a CI gate or local check when you need to
assess the project and its dependencies against the configured licence policy
without generating SPDX documents. The command writes no files by default.

## Inputs and example

Install the dependencies you intend to audit and select a language plugin that
provides project metadata. Configure `ACCEPTED_THIRD_PARTY_LICENCES` and any
documented manual reviews in `[ProjectConfig]` in `pyproject.toml`. Then run:

```bash
cd-check-licence-compliance
```

To keep the third-party IP summaries for review, create an output directory and
pass it to the command:

```bash
mkdir -p licensing
cd-check-licence-compliance --output-dir licensing
```

The optional `--output-dir` (`-o`) writes `third_party_IP_report.html`, `.csv`,
`.txt` and `.json`. It does not create `.spdx` files. The reports are written
before the compliance check, so they remain available if the check fails.

## Result

The command succeeds when the discovered project and dependency licences meet
the configured policy, including documented manual reviews. It fails if a
licence does not meet that policy, the selected plugin cannot supply metadata,
or report generation fails. If `FAIL_ON_INCOMPLETE_LICENCE_AUDIT` is enabled,
missing dependencies, unknown licences and undocumented exemptions also fail
the check. Results depend on the dependencies installed in the audited
environment.
The command also prints `ALLOW`, `REVIEW`, `MANUALLY_REVIEWED`, `DENY` and `UNKNOWN` dependency
counts. These advisory results do not change exit codes unless a project
explicitly opts into [assessment gating](assessing-dependency-licences.md).
Pass `--lookup-scancode` to consult
[ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/) for exact
identifiers whose category or assessment rule is missing. The lookup is opt-in; see
[dependency licence assessment](assessing-dependency-licences.md#optional-scancode-licensedb-lookup)
for the limits and report provenance.

To generate SPDX tag-value documents as well as reports, use
[`cd-generate-spdx`](generating-an-spdx-sbom.md). See
[third-party IP reporting](third-party-ip-reporting.md) for more on reviewing
the summaries and [project configuration](reading-project-configuration.md)
for the shared settings.
