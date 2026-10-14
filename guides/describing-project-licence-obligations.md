# Describe project licence obligations

## Problem and when to use it

Use `cd-describe-licence-obligations` when you want a quick human-readable
summary of the obligations attached to the project's configured licence.

The command resolves the project licence from `FILE_LICENCE_IDENTIFIER` and
combines data from SPDX.org, choosealicense.com and OSADL to explain the
licence in practical terms.

This command only covers projects configured with one exact SPDX identifier. It
does not cover compound expressions such as `Apache-2.0 OR MIT`.

## Inputs and example

Configure `FILE_LICENCE_IDENTIFIER` in `[ProjectConfig]` and run:

```bash
cd-describe-licence-obligations
```

## Output

The command prints a text report including:

- the SPDX identifier and licence name
- OSI approval when available
- choosealicense.com summary information
- permissions, conditions and limitations when available
- OSADL checklist obligations when available

For proprietary projects, CDS reports that the author must provide the full
licence text and that obligations need manual review against the custom terms.

Related commands:

- [`cd-sync-project-licence`](syncing-project-licence.md)
- [`cd-check-licence-compliance`](checking-licence-compliance.md)
