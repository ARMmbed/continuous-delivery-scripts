# Language and project plugin guides

CDS uses the project's `PROGRAMMING_LANGUAGE` setting to select a plugin.
Start with the landing page for your plugin, then follow its topic guides:

- [Basic](plugin-basic.md) — Git-based releases without a language-specific package.
- [CI](plugin-ci.md) — Releases for CI configuration projects.
- [Docker](plugin-docker.md) — Docker project integration.
- [GitHub Actions](plugin-github-actions.md) — CI workflow releases with GitHub integration.
- [Go](plugin-golang.md) — Go releases, modules and dependency preparation.
- [No-op](plugin-noop.md) — Projects that do not need language-specific steps.
- [Python](plugin-python.md) — Python package releases and dependency metadata.

The [general release guide](automating-releases.md) describes the shared CDS
workflow. Add future plugin-specific topic guides as Markdown files under
`guides/` and link them from the appropriate plugin landing page; the
documentation generator publishes these pages alongside the API reference.
