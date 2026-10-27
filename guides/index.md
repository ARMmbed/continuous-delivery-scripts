# Continuous Delivery Scripts: task guides

Use these guides to choose a command for a delivery task. All commands read
the shared project delivery definition from `[ProjectConfig]` in
`pyproject.toml`, regardless of language or CI system. Language plugins select
the ecosystem tools used for project-specific steps. The tools run in a Git
checkout with a Python environment; they are not tied to one CI provider.
The [API reference](https://armmbed.github.io/continuous-delivery-scripts/api.html) covers
the implementation, while these pages focus on inputs, outputs and examples.
For language-specific packaging, credentials and metadata support, start with
the [plugin guide index](plugin-guides.md).

## Choosing CDS

- [Why choose Continuous Delivery Scripts?](why-continuous-delivery-scripts.md): Understand CDS design goals, the specialised tools it uses, and when another approach may fit better.

## Dependency licences and OpenChain workflows

- [Assess dependency licence risks](assessing-dependency-licences.md): Review directional, explainable licence screening and optional project policy overrides.
- [Check licence compliance](checking-licence-compliance.md): Gate a project without generating SPDX files; optionally write reports.
- [Sync the project licence file](syncing-project-licence.md): Create or refresh the top-level project licence file from the configured SPDX identifier.
- [Describe project licence obligations](describing-project-licence-obligations.md): Summarise obligations for the configured project licence.
- [Generate an SPDX SBOM](generating-an-spdx-sbom.md): Produce project and dependency SPDX tag-value documents.
- [Generate a third-party IP / TPIP report](third-party-ip-reporting.md): Review dependency licences and compliance summaries.
- [Manage licence headers](licence-header-management.md): Apply copyright and SPDX headers to source files.

## Versioning and releases

- [Create a news fragment](creating-news-fragments.md): Describe one change before a release.
- [Check news fragments](checking-news-fragments.md): Require a valid fragment on a branch.
- [Preview a version](previewing-versions.md): Calculate a proposed project version.
- [Generate a changelog](managing-changelogs.md): Build release notes from news fragments.
- [Automate releases](automating-releases.md): Tag and publish with a language plugin.

## Plugin guides

- [Browse plugin guides](plugin-guides.md): Select the landing page for your plugin and its topic guides.

## Other project checks

- [Generate code documentation](generating-code-documentation.md): Build the API reference.
- [Check project configuration](checking-project-configuration.md): Validate CDS `ProjectConfig` values before running other commands.
- [Read project configuration](reading-project-configuration.md): Reuse values in scripts and CI.
- [Record accepted secret findings](recording-secrets.md): Maintain the detect-secrets baseline.
- [Check for new secrets](checking-for-secrets.md): Scan Git-tracked files in CI.
