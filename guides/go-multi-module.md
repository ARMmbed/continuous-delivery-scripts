# Go multi-module projects with CDS

[Go plugin guides](plugin-golang.md) · [All plugin guides](plugin-guides.md)

## Overview

Continuous Delivery Scripts (CDS) releases a **project**, not individual modules.
One repository can contain several independently consumable Go modules; they all
share the version calculated by CDS and are released together. The model follows
[go-openapi/swag](https://github.com/go-openapi/swag): versioned internal
requirements describe published dependencies, while local replacements support
development before those versions exist. See also the
[go-openapi CI workflows](https://github.com/go-openapi/ci-workflows).

## Split a monolithic project

For a project currently using `module github.com/example/my-project`, extract
packages into their own module directories and give each its own `go.mod`:

```text
my-project/
├── go.mod                 # optional root compatibility module
├── go.work                # optional workspace
├── core/go.mod
├── parser/go.mod
└── validator/go.mod
```

For example, run `go mod init github.com/example/my-project/core` from `core/`.
Repeat in each directory, using its actual published module path. A root module
can remain as a compatibility layer if it still provides the old packages; it
is not required. Update imports of moved packages yourself, or maintain
compatibility packages at the old paths. CDS does not rewrite source imports.
Check the [Go module reference](https://go.dev/ref/mod) and
[go.mod reference](https://go.dev/doc/modules/gomod-ref) when designing paths.

At the existing release `v1.2.0`, `core/go.mod` could contain:

```go
module github.com/example/my-project/core

go 1.24
```

`parser/go.mod` declares the published dependency and a local development path:

```go
module github.com/example/my-project/parser

go 1.24

require github.com/example/my-project/core v1.2.0

replace github.com/example/my-project/core => ../core
```

Go uses the local source from `../core` during module-mode development; the
`require` version describes what an external consumer will resolve. Replacements
in a dependency's `go.mod` are **not** inherited by that consumer. CDS preserves
both grouped and individual `replace` directives, and never adds or removes them.
For independent module-mode builds, provide local replacements for unpublished
internal versions. Ensure their directories exist and contain the expected
module's `go.mod`.

Alternatively, create `go.work` at the repository root:

```go
go 1.24

use (
    .
    ./core
    ./parser
    ./validator
)
```

Omit `.` if there is no root module. An active workspace resolves its listed
modules locally, even without module-level replacements. Workspace-level
replacements take precedence over conflicting module-level replacements. CDS
reads and checks local replacements in `go.work` but does not modify it.
See the [Go workspace tutorial](https://go.dev/doc/tutorial/workspaces).
To test a module without workspace resolution, run `GOWORK=off go test ./...`
from that module's directory; module-level replacements remain active.

## Coordinated release: v1.2.0 → v1.3.0

Suppose `parser` depends on `core`, and `validator` depends on both. Before
release preparation, `validator/go.mod` contains:

```go
module github.com/example/my-project/validator

go 1.24

require (
    github.com/example/my-project/core v1.2.0
    github.com/example/my-project/parser v1.2.0 // indirect
    github.com/external/library v1.4.0
)

replace (
    github.com/example/my-project/core => ../core
    github.com/example/my-project/parser => ../parser
)
```

CDS calculates the next **project** version `1.3.0` using its existing release
process.

### Module selection and eligibility

For a new version, the Go plugin uses the same module selection as
Go release tagging: the configured `SOURCE_DIR` and project root, plus modules
listed in `go.work` if present; otherwise, nested modules under `SOURCE_DIR`.
Set `SOURCE_DIR = "."` for the layout above, or list modules outside the source
directory in a root or source `go.work`. CDS does not scan other project-root
subdirectories for modules. It reads each selected `module` declaration using
Go tooling and matches `require` paths **exactly** against those declarations.
Modules need not be named after their directories or share a path prefix. A
duplicate declaration or malformed file among selected modules stops
preparation with an error.

CDS updates an internal requirement only when the requiring module has a
`replace` pointing to that exact module **inside this repository**, or the
requiring module is listed in `go.work use` and the dependency is either also
listed there or mapped to a repository-local module by a workspace `replace`.
A version-specific replacement must cover the upcoming version. Otherwise the
requirement stays unchanged, even if its module path is internal. Add local
resolution and rerun preparation before publication if that requirement must
reference the new release version.

### Result

After preparation, `parser/go.mod` requires `core v1.3.0`; the two internal
requirements in `validator/go.mod` become:

```go
require (
    github.com/example/my-project/core v1.3.0
    github.com/example/my-project/parser v1.3.0 // indirect
    github.com/external/library v1.4.0
)
```

The local replacements, external dependency, annotations, module and Go
directives remain intact. Files without eligible outdated requirements are not
rewritten. CDS stages only changed `go.mod` files with its normal release
changes. The existing tagging, changelog, versioning and publication steps
continue without module-specific release scheduling. The project release tag
is `v1.3.0`; subdirectory modules can also receive path-prefixed tags such as
`core/v1.3.0`, `parser/v1.3.0` and `validator/v1.3.0`, all on the same commit.

Go's `go mod edit` changes `require` versions without downloading the new
module versions. Local replacements or the active workspace allow testing
before those versions are published. CDS does not run `go get` or `go mod tidy`
and does not fabricate `go.sum` entries. If release validation runs outside
workspace mode, ensure each unpublished dependency has a local replacement.

## Validate development and publication

From each relevant module, run `go test ./...` with the workspace or valid
local replacements enabled. Inspect requirements and replacements with
[`go mod edit -json`](https://go.dev/ref/mod#go-mod-edit); from the workspace
directory, inspect its configuration with
[`go work edit -json`](https://go.dev/ref/mod#go-work-edit).

After publication, test actual published resolution in a **separate** consumer
directory, outside the original workspace and without local replacements:

```bash
mkdir release-check
cd release-check
go mod init example.com/release-check
go get github.com/example/my-project/validator@v1.3.0
go mod verify
go list -m all
go test ./...
```

`go test ./...` is meaningful once the consumer contains a Go package that
imports the released module. This check catches issues hidden by local source
resolution.

## Major-version migration

Go generally requires a matching `/v2` (or higher) suffix on module paths
and imports for major version 2 and above. For example:

```go
module github.com/example/my-project/core/v2
```

CDS updates eligible, compatible internal dependencies, such as `v2.1.0` →
`v2.2.0` for `core/v2`. A transition from an unsuffixed `core` at `v1` to `v2.0.0`
requires manual migration: change module declarations, source imports,
internal requirement paths and relevant replacements before preparing the
release. For an eligible internal requirement, CDS warns when it detects a
major-version transition requiring this migration and refuses to write an
incompatible version to `go.mod`. It does not migrate source code or release
modules independently. See
[Developing a major version update](https://go.dev/doc/modules/major-version).

## Troubleshooting

- **A future version cannot be fetched:** Use a valid local `replace` or a
  workspace listing the sibling module during preparation and testing.
- **A `go.mod` was not changed:** Check that CDS selects both module directories,
  that the `require` path matches the sibling's declaration exactly, and that
  its replacement or workspace resolution stays inside the repository.
- **A local replacement fails:** Confirm the target directory contains the
  correct module's `go.mod`. Workspace `use` entries also need existing
  module directories.
- **A consumer fails after publishing:** Local replacements do not propagate
  to consumers. Test with the isolated consumer above and inspect the released
  requirements and module tags.
- **A major-version release fails:** Update semantic import paths and imports
  manually before running CDS again.

Additional reading: [Go module version numbering](https://go.dev/doc/modules/version-numbers).
