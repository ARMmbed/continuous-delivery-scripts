# Sync the top-level project licence file

## Problem and when to use it

Use `cd-sync-project-licence` when a project has one exact SPDX licence
identifier in `FILE_LICENCE_IDENTIFIER` and you want CDS to create or refresh
the repository's top-level licence file from canonical public licence text.

This is useful when bootstrapping a project, standardising an existing
`LICENSE` file, or correcting drift before a release or compliance check.

The command only covers projects configured with one exact SPDX identifier. It
does not cover compound expressions such as `MIT OR Apache-2.0`.

## Inputs and example

Configure:

- `FILE_LICENCE_IDENTIFIER`
- `LICENCE_FILE_PATH` (defaults to `LICENSE`)

Then run:

```bash
cd-sync-project-licence
```

CDS fetches canonical text in this order when needed:

1. [ScanCode LicenseDB](https://scancode-licensedb.aboutcode.org/)
2. [SPDX.org](https://spdx.org/licenses/)
3. GitHub licences API
4. [choosealicense.com](https://choosealicense.com/)

## Output

If the file is missing, CDS creates it. If the file exists but differs from the
canonical text, CDS shows a diff in verbose mode and rewrites it. If the file
already matches, the command reports success without changing it.

For a proprietary project, CDS cannot fetch canonical text and instead requires
the author to provide the licence file manually.

Related commands:

- [`cd-check-licence-compliance`](checking-licence-compliance.md) for strict
  project and dependency licence checks
- [`cd-describe-licence-obligations`](describing-project-licence-obligations.md)
  for a summary of obligations
