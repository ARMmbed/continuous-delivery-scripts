# Generate changelogs from news fragments

## Problem and when to use it

Use `cd-generate-news` to turn one-line news fragments into release notes and
update the project version. This avoids manually editing a long changelog for
each pull request. Create fragments with
[`cd-create-news-file`](creating-news-fragments.md) and check them with
[`cd-assert-news`](checking-news-fragments.md).

## Inputs and example

Configure the Towncrier and versioning sections of `pyproject.toml`. Add a
fragment under `NEWS_DIR` for each change before building release notes:

```bash
cd-create-news-file "Fix dependency resolution" --type bugfix
cd-generate-news --release-type release
```

`--release-type` accepts `development`, `beta` or `release`. Beta and release
builds use news fragments; the command modifies version and changelog files,
so review the result before committing it.

## Output

The command prints the calculated version and, for beta or release builds,
updates the configured `CHANGELOG_FILE_PATH` from news fragments. See
[`cd-tag-and-release`](automating-releases.md) for the full publication flow.

## GitHub Actions example

After checkout with Git history and installing the project's dependencies:

```yaml
- run: cd-generate-news --release-type release
```

In a release pipeline, give subsequent steps access to the modified files
and push only with the team's chosen release permissions.
