# Check Git-tracked files for new secrets

## Problem and when to use it

Passwords, API tokens and other credentials can be committed to Git by
mistake. Once pushed, they may be exposed to anyone with repository access
and can remain in Git history even after the file is changed or deleted.
Reviewing every file manually before merging is unreliable.

Run `cd-detect-secrets` locally or in CI to check Git-tracked files against a
reviewed detect-secrets registry. It fails the check for new, unrecorded
findings so they can be investigated before a change is merged. It scans the
current checkout, not historical commits or untracked files. Use
[`cd-record-secrets`](recording-secrets.md) only for findings reviewed and
accepted by the team.

## Inputs and example

Install the project and its detect-secrets dependency, and keep the reviewed
registry under version control:

```bash
cd-detect-secrets --registry-file .secrets.baseline
```

The configured language plugin supplies exclusion patterns. Use
[`cd-record-secrets`](recording-secrets.md) only after reviewing an accepted
finding.

## Output

Exit status zero when tracked files match the registry; otherwise a failing
status with the detected findings.

## GitHub Actions example

After checkout and installation:

```yaml
- run: cd-detect-secrets
```

See [the repository's CI workflow](https://github.com/ARMmbed/continuous-delivery-scripts/blob/main/.github/workflows/ci.yml)
for an example of a separate secrets check.
