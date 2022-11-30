# Python plugin

This plugin is used for python projects when `PROGRAMMING_LANGUAGE` is set to `python`.

## Release
The plugin uses `wheel` to package the project before releasing it. 

The plugin uses twine to release packages to PYPI.
For that purpose, two environment variables need to be set:
- `TWINE_USERNAME`: the username of the PYPI account
- `TWINE_PASSWORD`: the password of the PYPI account

## Documentation
The plugin uses [pdoc](https://pdoc3.github.io/pdoc/) to generate the code reference documentation