# Record accepted secret-scan findings

## Problem and when to use it

Accidentally committing passwords, API keys or tokens to a Git repository can
expose them to anyone with access to the repository and its history. Even if
the file is later deleted, the secret may already have leaked. Use
[`cd-detect-secrets`](checking-for-secrets.md) to catch new findings before
they are committed or merged.

`cd-record-secrets` maintains the detect-secrets baseline used by that check.
Run it **only after reviewing findings** to record known, acceptable values
that would otherwise be reported again. Do not add a real secret to the
baseline to silence the check; if one was committed, remove it and rotate the
credential.

## Inputs and example

Run from a configured project with `detect-secrets` installed. The registry
path defaults to `SECRETS_BASELINE_FILENAME` and can be overridden:

```bash
cd-record-secrets --registry-file .secrets.baseline
```

The project plugin supplies exclusion patterns for generated or unsuitable
files. Review the diff before committing the registry.

## Output

An updated secret-registry file in the project checkout. Use
[`cd-detect-secrets`](checking-for-secrets.md) to check tracked files against
it in CI.

## GitHub Actions example

For a reviewed baseline refresh, after checkout and installation:

```yaml
- run: cd-record-secrets --registry-file .secrets.baseline
- run: git diff -- .secrets.baseline
```

Commit the change only after reviewing accepted findings.
