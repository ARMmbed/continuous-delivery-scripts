# Automate semantic versioning, Git tags and releases

## Problem and when to use it

Use `cd-tag-and-release` to orchestrate a configured release instead of
repeating versioning, documentation, Git tagging, packaging and publication
steps in each CI system. The shared release definition comes from
`[ProjectConfig]` in `pyproject.toml`. A language plugin supplies
project-specific actions using the tools best suited to its language.
Publication destinations also depend on the plugin. See
[changelog management](managing-changelogs.md) for the
news fragments used to calculate release versions.

## Inputs and example

Run from a configured Git checkout with installed dependencies, a writable
remote and the credentials required by the selected language plugin. The
[plugin documentation](https://github.com/ARMmbed/continuous-delivery-scripts/tree/main/continuous_delivery_scripts/plugins)
describes packaging, publication and credential requirements for each language.
Use a release type of `development`, `beta` or `release`:

```bash
cd-determine-version --release-type release
cd-tag-and-release --release-type release --current-branch main
```

The first command previews the proposed version. The second can commit, tag,
push and publish; run it only in an authorised release workflow. `development`
does not publish a production release.

## Output

A production release updates release notes, documentation and tags, and the
plugin publishes its package or other configured output. The exact output
varies by plugin; see the [release workflow](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/.github/workflows/release.yml).

## GitHub Actions example

After checkout and installing the project's release dependencies:

```yaml
- run: cd-tag-and-release --release-type release --current-branch "$GITHUB_REF_NAME"
  env:
    GIT_TOKEN: ${{ secrets.RELEASE_TOKEN }}
```

Configure the Git token for GitHub-hosted repositories and add the credentials
required by the selected plugin; see its documentation for details.
Related commands: [`cd-determine-version`](previewing-versions.md) and
[`cd-generate-news`](managing-changelogs.md).
