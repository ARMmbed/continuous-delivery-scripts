# Golang plugin

This plugin is used for golang projects when `PROGRAMMING_LANGUAGE` is set to `golang`.

In order to work, `go > 1.18` is required.

## Release
The plugin leverages [goreleaser](https://goreleaser.com/) to package and release projects.
Therefore, a `.goreleaser.yml` file must be present in the go source directory i.e. where the mod file lies.

## Documentation
The plugin uses [doc2go](https://abhinav.github.io/doc2go) to generate the code reference documentation.

## SPDX and third-party IP reporting

The Go plugin uses [go-licenses v2](https://github.com/google/go-licenses) to
discover the licences of packages imported by Go modules. It checks for a
usable `go-licenses` binary on `PATH` before installing
`github.com/google/go-licenses/v2@latest` with `go install`. The Go toolchain
must be available; an installed binary can also be located under `GOBIN` or
the first `GOPATH` entry's `bin` directory.

Set `PROGRAMMING_LANGUAGE = "golang"`, `PROJECT_NAME`, `PROJECT_ROOT` and
`SOURCE_DIR` in `[ProjectConfig]`. Put a `go.mod` under the source or project
root; `go.work` modules and nested Go modules are also considered. Supply
`FILE_LICENCE_IDENTIFIER` for the project licence and set `PROJECT_UUID`
and `[spdx]` namespace fields as explained in the
[SPDX configuration guide](../../DEVELOPMENT.md#spdx-document-identity).

With the project and its Go dependencies available, run:

```bash
mkdir -p licensing
cd-generate-spdx --output-dir licensing
```

For each module, the plugin runs `go-licenses report ./...` with a template
to collect dependency package names, versions, licence URLs and SPDX licence
names. The [go-licenses custom-template documentation](https://github.com/google/go-licenses/blob/master/README.md#reports-with-custom-templates)
defines the `Name`, `Version`, `LicenseURL` and `LicenseName` fields used by the
plugin; the default CSV report has no `Version` field. The metadata then enters
the **shared** SPDX writer, HTML/CSV/text/JSON
third-party IP report and accepted-licence policy used by other plugins.
To include the shared licence summary in release documentation, set
`GENERATE_LICENSING_SUMMARY_ON_RELEASE = true` in `[ProjectConfig]` (the default
is `false`).
The Go tool's own `check` policy is not used; configure
`ACCEPTED_THIRD_PARTY_LICENCES` and documented exceptions in
`PACKAGES_WITH_CHECKED_LICENCE` in `pyproject.toml` instead. Unknown licences
remain unknown so that the shared audit can flag them. The report reflects
dependencies built for the current Go environment and excludes test-only
imports unless the Go tool is invoked separately with `--include_tests`.
