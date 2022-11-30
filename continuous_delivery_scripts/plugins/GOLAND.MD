# Golang plugin

This plugin is used for golang projects when `PROGRAMMING_LANGUAGE` is set to `golang`.

In order to work, `go > 1.18` is required.

## Release
The plugin leverages [goreleaser](https://goreleaser.com/) to package and release projects.
Therefore, a `.goreleaser.yml` file must be present in the go source directory i.e. where the mod file lies.

## Documentation
The plugin uses [golds](https://github.com/go101/golds) to generate the code reference documentation.
It currently uses version 0.4.1 as later versions comprise [an issue](https://github.com/go101/golds/issues/26)