# Golang plugin

This plugin is used for golang projects when `PROGRAMMING_LANGUAGE` is set to `golang`.

In order to work, `go > 1.18` is required.

## Release
The plugin leverages [goreleaser](https://goreleaser.com/) to package and release projects.
Therefore, a `.goreleaser.yml` file must be present in the go source directory i.e. where the mod file lies.

## Documentation
The plugin uses [doc2go](https://abhinav.github.io/doc2go) to generate the code reference documentation.
