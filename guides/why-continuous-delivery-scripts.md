# Why choose Continuous Delivery Scripts?

## Problem and when to read this

Read this guide when you are deciding whether CDS fits a project's release and
delivery workflow, or when you need to explain why CDS exists alongside other
release automation tools.

CDS is not primarily trying to infer releases from Git history or prescribe one
CI/CD platform. It tries to answer a different question: how can a project keep
consumer-facing release information, delivery policy and automation consistent
without coupling them to one commit convention, language ecosystem or CI system?

## What CDS is trying to solve

CDS provides reusable commands for software delivery tasks such as changelog
generation, version calculation, release orchestration, SPDX SBOM generation,
licence reporting, documentation publishing and secret checks.

The tools share one project configuration in `[ProjectConfig]` and can be run
locally or from different CI systems. Language plugins then use the most
appropriate ecosystem tools for project-specific work.

## Design principles

### Separate development history from consumer-facing changes

Git commits and release notes serve different audiences.

- Git history records implementation details for maintainers.
- Release notes explain user-visible impact for consumers.

Following [Towncrier's philosophy](https://towncrier.readthedocs.io/), CDS uses
explicit news fragments rather than deriving release notes from commit messages.
This avoids forcing one commit message to serve both maintainers and consumers.

### Keep release management independent of CI/CD platforms

CDS provides command-line tools that can be invoked from GitHub Actions,
Jenkins, GitLab CI or other automation environments. The delivery policy lives
in project configuration and scripts, not in one CI provider's release model.

### Prefer composable tools over monolithic workflows

CDS follows a small-tools approach. Projects can adopt only the commands they
need instead of taking an all-or-nothing release framework.

Examples include:

- validating news fragments and generating changelogs
- determining versions and coordinating releases
- generating SPDX SBOMs and third-party IP reports
- managing licence files and source headers
- generating project documentation
- checking Git-tracked files for new secrets

### Treat software delivery as more than versioning and tagging

Releases often involve documentation, provenance, licensing, dependency review,
packaging and publication. CDS brings those concerns into one delivery toolkit
instead of treating a release as only version calculation and Git tagging.

### Support coordinated project releases

CDS takes a project-oriented approach. A repository may contain several
packages, modules or deliverables but still share one project version,
changelog and release flow. This is particularly useful for coordinated
multi-module Go releases.

## CDS often uses specialised tools rather than replacing them

CDS is often a coordinator around established tools instead of a reimplementation
of them. In this repository and its plugins, that includes:

- [Towncrier](https://towncrier.readthedocs.io/) for consumer-facing changelog generation from news fragments
- [GoReleaser](https://goreleaser.com/) in the Go plugin for packaging and publication steps
- Python build tools such as wheel and [Twine](https://twine.readthedocs.io/) in the Python plugin
- [pdoc](https://pdoc.dev/) and doc2go through the documentation workflow
- [detect-secrets](https://github.com/Yelp/detect-secrets) for reviewed secret scanning baselines
- SPDX data and optional [ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/) lookups for licensing workflows

This is an important distinction: CDS aims to give projects a consistent command
surface and shared delivery policy, while still relying on specialised tooling
where that tooling is the best fit.

## How CDS compares with other approaches

| Approach | Primary focus | Key distinction from CDS |
| --- | --- | --- |
| [release-please](https://github.com/googleapis/release-please) | Conventional Commits, release PRs and GitHub Releases | Derives release information mainly from commit history and is closely integrated with GitHub workflows. |
| [semantic-release](https://semantic-release.gitbook.io/) | Fully automated semantic releases | Uses commit conventions to determine release significance and automate publishing. |
| [Changesets](https://github.com/changesets/changesets) | Explicit change declarations and package versioning | Shares explicit change tracking, but focuses more on package-level versioning and monorepo publishing flows. |
| [Towncrier](https://towncrier.readthedocs.io/) | Consumer-focused changelog generation | Shares CDS's news-fragment philosophy but does not provide the broader release, documentation and compliance command set. |
| [release-it](https://github.com/release-it/release-it) | Configurable release automation | Provides an extensible release engine rather than CDS's wider collection of delivery and compliance utilities. |
| [GoReleaser](https://goreleaser.com/) | Building, packaging and distributing Go applications | Focuses on release artefact production and distribution rather than defining a project-wide delivery policy. |

These approaches are not mutually exclusive. CDS can complement specialised
tools when their strengths match part of a project's workflow.

## When CDS is a good fit

CDS is particularly suitable when:

- you want release notes to describe consumer impact independently of commit history
- you need consistent release practices across multiple projects or languages
- you want release tooling that is portable across CI/CD platforms
- you prefer composable commands over one monolithic workflow
- you need licensing, SBOM, documentation and release tasks in one toolkit
- you want to coordinate several deliverables as one project release

Other approaches may be more suitable when:

- the project already relies on Conventional Commits and wants releases derived directly from them
- you want a ready-made GitHub-native release PR workflow with minimal orchestration
- you need independently versioned packages inside a monorepo
- you mainly need artefact building and distribution rather than broader delivery policy and compliance workflows

## Summary

CDS treats release management as a distinct concern from development history and
provides reusable building blocks for implementing consistent, portable software
delivery processes.

Its purpose is not to replace every specialised tool, but to avoid coupling
release communication, project policy and delivery automation to one commit
convention, programming language or CI/CD platform.
