# Require a valid news fragment on a branch

## Problem and when to use it

Use `cd-assert-news` as a PR gate when every change needs a release note. It
checks for a news fragment added on the branch and validates its filename and
one-line content. A configured dependency-update branch may receive an
automatically generated fragment when none exists.

## Inputs and example

Use a Git checkout containing the branch and its base history, with `NEWS_DIR`
configured in `pyproject.toml`. Developers can check their current checkout:

```bash
cd-assert-news --local
```

In CI, pass the PR head branch using `--current-branch` so the tool checks the
correct branch. Non-local mode may clone, commit and push a missing fragment;
configure credentials for that automation.

## Automatically generate fragments for dependency upgrades

Dependency-update branches, such as Dependabot PRs, can be given a news
fragment automatically when one is **missing**. Configure the behaviour in
`[ProjectConfig]` in `pyproject.toml`:

```toml
NEWS_DIR = "news/"
AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE = true
DEPENDENCY_UPDATE_BRANCH_PATTERN = '^dependabot/[^/]+/(?P<DEPENDENCY>.+)$'
DEPENDENCY_UPDATE_NEWS_MESSAGE = "Dependency upgrade: {message}"
DEPENDENCY_UPDATE_NEWS_TYPE = "bugfix"
```

The regex identifies eligible branches and captures the dependency name. For
example, `dependabot/pip/requests-2.32.3` produces a `bugfix` fragment with
the text `Dependency upgrade: requests-2.32.3`. The `{message}` placeholder
receives the captured group values, joined by commas if there is more than
one. Set `AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE = false` to require
manually added fragments even on those branches.

On each run, `cd-assert-news` checks for a fragment added in the latest commit
and, if none is found there, checks the whole branch. Existing fragments are
validated rather than duplicated. **Only when no fragment exists** does it
check the branch pattern and the automatic-generation setting. An invalid
existing fragment fails validation; it is not replaced by another file.

If eligible, the command creates a timestamped fragment, commits it to the
branch and, outside `--local` mode, pushes it back to the remote. The run
still exits with a failing status so CI can recheck the updated branch on the
next run. The remote workflow therefore needs credentials that permit a push;
Dependabot-triggered workflows may not receive repository secrets on their
initial run. Other branches with no fragment continue to fail the check.

## Output

Success when the branch has a valid fragment; a failing exit status for a
missing or invalid one. Use [`cd-create-news-file`](creating-news-fragments.md)
to write a fragment before running the check.

## GitHub Actions example

After fetching the full Git history and installing the tool:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- run: cd-assert-news --current-branch "$HEAD_BRANCH"
  env:
    HEAD_BRANCH: ${{ github.head_ref }}
    GIT_TOKEN: ${{ secrets.GIT_SECRET }}
```

Configure a token with the permissions needed to push automatic fragments.
See the repository's [CI example](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/.github/workflows/ci.yml)
for the branch argument and token configuration.
