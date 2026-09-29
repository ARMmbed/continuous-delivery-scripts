# Preview a semantic release version

## Problem and when to use it

Use `cd-determine-version` to see the project version a release type would
produce before running steps that modify the changelog, Git tags or packages.
It calculates a project version, not the installed tool's version.

## Inputs and example

In a configured Git checkout with version and news-file settings:

```bash
cd-determine-version --release-type release
```

Choose `development`, `beta` or `release` according to the intended flow.

## Output

The proposed version is printed to standard output; the command does not
generate a changelog. Use [`cd-generate-news`](managing-changelogs.md) when
the release files should be updated.

## GitHub Actions example

After checkout with history and installation:

```yaml
- run: cd-determine-version --release-type release
```

Related command: [`cd-tag-and-release`](automating-releases.md).
