# Create a news fragment for a change

## Problem and when to use it

When several changes are developed in parallel, editing one shared changelog
for every pull request is easy to forget and can cause merge conflicts. Commit
messages record details for developers, but do not necessarily explain a
change's impact to people using the project. A **news fragment** is a small,
one-line, user-facing description of a single change, committed alongside the
change rather than editing the release notes directly.

Use `cd-create-news-file` while developing a change so its release note is
recorded before a pull request. At release time,
[`cd-generate-news`](managing-changelogs.md) collects the fragments into the
changelog. See the [Contributing guide's News Files section](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/CONTRIBUTING.md#news-files)
for the purpose, required format and change-type extensions of fragments.

## Inputs and example

Configure `NEWS_DIR` and Towncrier in `pyproject.toml`. Supply one line of text
and optionally a type (`bugfix`, `feature`, `doc`, `major`, `misc` or `removal`):

```bash
cd-create-news-file "Fix dependency resolution" --type bugfix
```

## Output

A numbered file is created in the configured news directory. Commit the file
with the change it describes. The default type is `feature`; use
`--ref-number` when a specific numeric reference is required.

## GitHub Actions example

Normally developers create and commit fragments locally. A workflow may
create one for an automated change after checkout and installation:

```yaml
- run: cd-create-news-file "Update build dependency" --type bugfix
```

The workflow must commit and push the file if it should appear in a PR.
Related command: [`cd-assert-news`](checking-news-fragments.md).
