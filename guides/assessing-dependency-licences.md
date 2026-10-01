# Assess dependency licence risks

## What this assessment does

The existing third-party IP report screens each discovered dependency against
the **project's declared licence**, as provided by the selected language
plugin. No second dependency scan or extra project-licence setting is needed.
This directional screening highlights possible obligations; it cannot decide
whether a particular use, linking arrangement or distribution is legally
permitted. The existing accepted-licence policy and manual reviews remain a
separate compliance check.

The automatic screen produces one of four results for each dependency. A
documented manual review moves an automatic `REVIEW` to `MANUALLY_REVIEWED`:

| Assessment | Meaning |
| --- | --- |
| `ALLOW` | An identified, low-risk combination under the screening rules. Licence notices and conditions still apply. |
| `REVIEW` | Additional facts or obligations need human review; this is not a finding of infringement. |
| `MANUALLY_REVIEWED` | A `REVIEW` has a matching project review record and explanation. The automatic `REVIEW`, reason and rule remain visible. |
| `DENY` | An explicit project prohibition or narrowly specified directional rule applies. |
| `UNKNOWN` | A licence or usable project declaration is missing or cannot be classified reliably. |

Every result includes a reason, the rule ID, and whether the rule came from the
embedded policy or a project override. HTML and text reports show counts for
each outcome; JSON and CSV expose per-dependency values. Missing dependencies
are listed separately as audit gaps because no licence was discovered for them.
No screening decision is written into the SPDX documents.

## Default rules and expressions

The [embedded TOML policy](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/continuous_delivery_scripts/spdx_report/data/licence_assessment.toml)
is loaded automatically. Its explicit SPDX classifications draw on the
approach used by [OSS Review Toolkit](https://www.oss-review-toolkit.org/ort/docs/configuration/license-classifications)
and [ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/). They are
screening categories, not legal conclusions. For a BSD-3-Clause project, MIT,
BSD-3-Clause and Apache-2.0 dependencies normally receive `ALLOW`, while
LGPL, GPL and AGPL dependencies receive `REVIEW` with a reason. A proprietary
project declared as `LicenseRef-Proprietary` gets the same conservative
screening; unclassified custom `LicenseRef-*` terms require review.

Expressions use the installed SPDX expression parser, not string splitting:

- `MIT OR GPL-3.0-only` can select MIT and records the selected choice.
- `MIT AND GPL-3.0-only` considers both sets of obligations and is marked `REVIEW`.
- A `WITH` exception needs an explicit rule for the full expression; otherwise
  it receives `REVIEW`. `-only` and `-or-later` are distinct identifiers.
- An unknown project or dependency licence receives `UNKNOWN`; an unclassified
  project licence needs `REVIEW` rather than an assumed permissive category.

If discovery reports an **unknown dependency licence**, or finds an expression
that results in an `UNKNOWN` assessment, the project can provide a verified
SPDX expression in its existing `PACKAGES_WITH_CHECKED_LICENCE` table. Risk
screening uses the verified value only when the original assessment is
`UNKNOWN`:

```toml
[ProjectConfig.PACKAGES_WITH_CHECKED_LICENCE]
click-default-group = "BSD-3-Clause"
```

Suppose `click-default-group` is installed but its package metadata reports
`Unknown`, and the project declares `Apache-2.0`. With the entry above, the
report makes the two sources of information distinct:

| Report field | Value | Meaning |
| --- | --- | --- |
| Discovered licence | `Unknown` | No usable licence was found in the package metadata. The package row and SPDX output are not rewritten to claim discovery found BSD-3-Clause. |
| Assessed dependency licence | `BSD-3-Clause` | The human-verified value from `PACKAGES_WITH_CHECKED_LICENCE`, labelled **manual licence review** in the assessment. |
| Risk assessment | `ALLOW` | The existing `permissive-dependency` rule screens BSD-3-Clause against the project's Apache-2.0 licence. This does not waive BSD notice obligations. |
| Unknown-licence audit gap | Still listed | Metadata discovery remains incomplete even though the manually verified licence was usable for assessment. |

An entry such as `click-default-group = "Accepted because it is not distributed"`
is an exemption explanation, **not** an SPDX licence expression. It may still
serve as a manual allowlist record, but the risk assessment remains `UNKNOWN`.
Only a recognised SPDX expression (or a valid `LicenseRef-*`) is used as a
manually verified assessment input.

Legacy flat entries with an explicit choice are also recognised. For example,
`packaging = "either Apache-2.0 or BSD-2-Clause"` assesses the dependency under
`Apache-2.0 OR BSD-2-Clause`. The recorded explanation for `python-dateutil`,
`All contributions after December 1, 2017 released under dual license - either
Apache 2.0 License or the BSD 3-Clause License.`, becomes `Apache-2.0 OR
BSD-3-Clause`. Each named alternative must match an SPDX licence exactly after
normalising standard names; unrelated prose or a fuzzy match is rejected.
The prose fallback recognises a leading `either` or an explicit `dual licence`
or `licensed under` introduction. Negations, illustrative examples and extra
conditions are not inferred as licence choices; use the structured form below
when the wording is more complex.

For new entries, put the verified expression and its review rationale in
separate fields instead of embedding an expression inside prose:

```toml
[ProjectConfig.PACKAGES_WITH_CHECKED_LICENCE.packaging]
licence = "Apache-2.0 OR BSD-2-Clause"
reason = "Verified against the packaged Apache and BSD licence files."
```

For `regex`, the project currently records `Apache-2.0`, but package metadata
declares `Apache-2.0 AND CNRI-Python`, which has no complete screening rule.
The manual value can be assessed, while the original expression remains visible
in the report and SPDX output. An `ALLOW` for the manually entered Apache
licence **does not establish that the CNRI-Python obligations disappeared**:
review any terms left out of the manual value before relying on the result.

## Optional ScanCode LicenseDB lookup

If an SPDX identifier is not classified locally or a directional assessment
rule is missing, opt in to a bounded lookup of the public
[ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/) index:

```bash
cd-check-licence-compliance --lookup-scancode --output-dir licensing
cd-generate-spdx --lookup-scancode --output-dir licensing
```

Create the output directory first, or omit `--output-dir` from the check-only
command if no report files are needed. Lookups are **off by default**; when
enabled, the index is fetched at most once per command run,
with a timeout. Only exact SPDX licence identifiers are matched: it cannot
infer a missing licence from a dependency name or decipher an arbitrary
`LicenseRef-*`. Project and embedded classifications always take precedence.

[ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/) supplies licence
categories and links to licence records, **not project/dependency compatibility
verdicts**. The mapping from its categories
to assessment categories is in the embedded policy's `scancode_categories`
table and can be overridden in either project policy format. A previously
unclassified permissive licence may therefore follow an existing screening
rule, but an absent directional rule still yields `REVIEW`, not an invented
decision. Unrecognised categories, unavailable network access and missing
identifiers retain the conservative assessment; use `-v` to see lookup
warnings. Consulted categories and URLs are recorded in the reports and
printed by the check-only command. SPDX output and the accepted-licence policy
are unchanged by this option.

After a **successful** lookup-assisted command, warnings on standard error
identify each consulted licence, its
[ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/) source URL and
the local action needed to make future runs reproducible without the flag. For
example, after
checking the terms at the supplied URL, add a verified SPDX classification to
`[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications]` (or to the project
policy file). If a category is already defined but no directional rule applies,
the warning instead asks for a rule under
`[[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]]` with a documented reason.
Run the command without `--lookup-scancode` to verify the local policy works.
Warnings are not printed as successful remediation advice when the compliance
check fails. External categories are evidence for review, not a substitute for
reviewing licence terms or the separate accepted-licence policy.

## Record a manual assessment review

After reviewing a dependency with an automatic `REVIEW` result, add a reason
under `[ProjectConfig.REVIEWED_LICENCE_ASSESSMENTS]` in `pyproject.toml`:

```toml
[ProjectConfig.REVIEWED_LICENCE_ASSESSMENTS.bar]
licence = "LGPL-2.1-only"
version = "2.0"
reason = "Reviewed linking and distribution obligations (LEGAL-42)."
```

The package name must match the discovered dependency. Matching its licence
and version prevents the record applying after its terms or version change.
For an unscoped review, `bar = "Review reason"` can instead be written directly
under `[ProjectConfig.REVIEWED_LICENCE_ASSESSMENTS]`; the scoped form is
recommended. A blank reason is invalid. A matching record changes the reported
status and counts to `MANUALLY_REVIEWED` but preserves the automatic `REVIEW`
and its rule. It does not turn `DENY` or `UNKNOWN` into reviewed outcomes.

If `fail_on = ["REVIEW"]` was configured, the matching review clears **that**
assessment gate. The existing accepted-licence check remains independent: for
an LGPL dependency not on the accepted list, also record its approval under
`[ProjectConfig.PACKAGES_WITH_CHECKED_LICENCE]` (or explicitly accept the
licence). The report keeps both explanations separately.

## Override the embedded policy when necessary

Projects **do not need to supply any policy**: embedded rules are applied
automatically. For a small override, put the same policy tables directly in
the project's `pyproject.toml`:

```toml
[ProjectConfig.LICENCE_ASSESSMENT_RULES]
schema_version = 1

[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]
fail_on = ["DENY"]

[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications]
LicenseRef-Internal = "PROPRIETARY"

[[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]]
id = "review-internal-vendor"
project_licence = "LicenseRef-Proprietary"
dependency_licence = "LicenseRef-Internal"
status = "REVIEW"
reason = "Check the agreement for this licence before distribution."

[[ProjectConfig.LICENCE_ASSESSMENT_RULES.packages]]
id = "vendor-1.2-agreement"
name = "vendor"
version = "1.2"
status = "ALLOW"
reason = "Reviewed the vendor agreement for version 1.2."
```

For a larger policy, alternatively set a path under `[ProjectConfig]` in
`pyproject.toml`. The path is resolved relative to that file:

```toml
[ProjectConfig]
LICENCE_ASSESSMENT_RULES_PATH = "policy/licence-assessment.toml"
```

For example, the project file could contain:

```toml
schema_version = 1

[settings]
fail_on = ["DENY", "UNKNOWN"]

[classifications]
LicenseRef-Internal = "PROPRIETARY"

[[rules]]
id = "strong-copyleft-dependency"
project_category = "*"
dependency_category = "STRONG_COPYLEFT"
status = "DENY"
reason = "Our organisation does not distribute combined works under these terms."

[[rules]]
id = "review-internal-vendor"
project_licence = "LicenseRef-Proprietary"
dependency_licence = "LicenseRef-Internal"
status = "REVIEW"
reason = "Check the agreement for this licence before distribution."

[[packages]]
id = "vendor-1.2-agreement"
name = "vendor"
version = "1.2"
status = "ALLOW"
reason = "Reviewed the vendor agreement for version 1.2."
```

The order is **embedded defaults → project policy file → inline tables**. If
both project options are present, the inline values win. Classifications
override by licence ID; rules override by stable `id`, and unmentioned defaults
remain in effect. Use the same `schema_version`, `settings`,
`classifications`, `rules` and `packages` keys with either project option.
Package exceptions match a dependency name and optional exact version before
general rules, including when its licence is otherwise unknown. For rules,
an exact directional licence match takes precedence over a category match;
conflicting rules of equal specificity fail validation. A `*` project category
matches only classified project licences. Invalid or missing override files
and invalid inline tables cause a clear error rather than silently reverting to
defaults.

The embedded `fail_on = []` keeps existing CI exit codes unchanged. An optional
project `fail_on` list can gate on `DENY` or `DENY` and `UNKNOWN`; unreviewed
`REVIEW` results only fail when explicitly configured. The
pre-existing accepted-licence check can still fail independently of these
assessments. See [third-party IP reporting](third-party-ip-reporting.md) and
the [check-only command](checking-licence-compliance.md) for generating and
reviewing the results.
