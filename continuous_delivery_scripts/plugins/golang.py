#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Golang projects."""

import json
import logging
import os
import shutil
from pathlib import Path
from subprocess import check_call, check_output
from typing import TYPE_CHECKING, Optional, List, Dict, MutableMapping

from continuous_delivery_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import (
    LocalProjectRepository,
    GitWrapper,
)
from continuous_delivery_scripts.utils.language_specifics_base import (
    BaseLanguage,
    get_language_from_file_name,
)

if TYPE_CHECKING:
    from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject

logger = logging.getLogger(__name__)

SRC_DIR = Path(str(configuration.get_value(ConfigurationVariable.SOURCE_DIR)))
ROOT_DIR = Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))
ENVVAR_GORELEASER_GIT_TOKEN = "GITHUB_TOKEN"
ENVVAR_GORELEASER_CUSTOMISED_TAG = "GORELEASER_CURRENT_TAG"
ENVVAR_GO_MOD = "GO111MODULE"
GO_MOD_ON_VALUE = "on"


def _generate_doc2go_command_list(output_directory: Path, module: str) -> List[str]:
    return [
        "doc2go",
        "-out",
        str(output_directory),
        f"{module}",
    ]


def _generate_goreleaser_release_command_list(changelog: Path) -> List[str]:
    return [
        "goreleaser",
        "release",
        "--clean",
        "--release-notes",
        f"{str(changelog)}",
    ]


def _generate_goreleaser_check_command_list() -> List[str]:
    return [
        "goreleaser",
        "check",
    ]


def _install_doc2go_command_list() -> List[str]:
    return [
        "go",
        "install",
        "go.abhg.dev/doc2go@latest",
    ]


def _install_syft_command_list() -> List[str]:
    return ["go", "install", "github.com/anchore/syft/cmd/syft@latest"]


def _install_goreleaser_command_list() -> List[str]:
    return ["go", "install", "github.com/goreleaser/goreleaser/v2@latest"]


def _ensure_go_tool_installed(
    tool_name: str,
    version_command: List[str],
    install_command: List[str],
    env: MutableMapping[str, str],
) -> None:
    """Ensure a Go-based tool is available on PATH before use."""
    tool_path = shutil.which(tool_name)
    if tool_path:
        try:
            check_output(version_command, env=env)
            logger.info("Using %s from PATH: %s", tool_name, tool_path)
            return
        except Exception as exception:
            logger.warning("Could not use %s from PATH: %s", tool_name, exception)

    logger.info("Installing %s with go install.", tool_name)
    check_call(install_command, env=env)


def _call_doc2go(output_directory: Path, module: str) -> None:
    """Call doc2go for generating the docs."""
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    _ensure_go_tool_installed(
        tool_name="doc2go",
        version_command=["doc2go", "-version"],
        install_command=_install_doc2go_command_list(),
        env=env,
    )
    logger.info("Creating Code documentation.")
    logger.info("Running doc2go over [%s] in [%s].", module, SRC_DIR)
    # FIXME enable doc2go when fully tested
    # check_call(
    #    _generate_doc2go_command_list(output_directory, module),
    #    cwd=str(SRC_DIR),
    #    env=env,
    # )
    logger.warning("Currently not running doc2go")


def _call_goreleaser_check(version: str) -> None:
    """Calls go releaser check to verify configuration."""
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    _ensure_go_tool_installed(
        tool_name="syft",
        version_command=["syft", "--version"],
        install_command=_install_syft_command_list(),
        env=env,
    )
    _ensure_go_tool_installed(
        tool_name="goreleaser",
        version_command=["goreleaser", "--version"],
        install_command=_install_goreleaser_command_list(),
        env=env,
    )
    logger.info("Checking GoReleaser configuration.")
    env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = version
    env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_goreleaser_check_command_list(), cwd=ROOT_DIR, env=env)


def _determine_go_module_tag_for_directory(module_directory: Path, version: str) -> Optional[str]:
    try:
        module = str(module_directory.relative_to(ROOT_DIR))
    except ValueError:
        try:
            module = str(ROOT_DIR.relative_to(module_directory))
        except ValueError as exception:
            logger.warning(exception)
            return None
    if module == "." or len(module) == 0:
        return None
    module = module.replace("\\", "/").rstrip("/")
    return f"{module}/{version}"


def _find_go_work_files() -> List[Path]:
    go_work_files: List[Path] = []
    for go_work_file in [SRC_DIR.joinpath("go.work"), ROOT_DIR.joinpath("go.work")]:
        if go_work_file.exists() and go_work_file not in go_work_files:
            go_work_files.append(go_work_file)
    return go_work_files


def _determine_go_work_module_directories_from_json(go_work_file: Path) -> List[Path]:
    """Determine module directories from `go work edit -json` output.

    `go.work` lists all workspace modules that should be released together.
    See https://go.dev/ref/mod#workspaces and https://pkg.go.dev/cmd/go#hdr-Edit_workspace_file.
    """
    go_work_root = go_work_file.parent
    go_work = json.loads(check_output(["go", "work", "edit", "-json"], cwd=go_work_root, encoding="utf8"))
    module_directories: List[Path] = []
    for use_definition in go_work.get("Use", []):
        disk_path = use_definition.get("DiskPath") or use_definition.get("Path")
        if not disk_path:
            continue
        module_directory = Path(str(disk_path))
        module_directories.append(
            module_directory if module_directory.is_absolute() else go_work_root.joinpath(module_directory)
        )
    return module_directories


def _determine_go_work_module_directories() -> List[Path]:
    """Determine module directories declared in `go.work`.

    `go.work` lists all workspace modules that should be released together.
    See https://go.dev/ref/mod#workspaces.
    """
    module_directories: List[Path] = []
    for go_work_file in _find_go_work_files():
        module_directories.extend(_determine_go_work_module_directories_from_json(go_work_file))
    return list(dict.fromkeys(module_directories))


def _determine_go_subproject_directories() -> List[Path]:
    if not SRC_DIR.exists():
        return []
    return sorted((go_mod_file.parent for go_mod_file in SRC_DIR.rglob("go.mod")), key=lambda path: str(path))


def _determine_go_module_tag(version: str) -> List[str]:
    """Determine all go module tags for release.

    See https://golang.org/ref/mod#vcs-version,
    https://go.dev/ref/mod#workspaces, and
    https://github.com/golang/go/wiki/Modules/a549b3e4b7ad6be6e7d11c37ef247bb2279c8146#faqs--multi-module-repositories.
    """
    module_directories = [SRC_DIR]
    go_work_module_directories = _determine_go_work_module_directories()
    if go_work_module_directories:
        module_directories.extend(go_work_module_directories)
    else:
        module_directories.extend(_determine_go_subproject_directories())

    tags = [
        _determine_go_module_tag_for_directory(module_directory, version) for module_directory in module_directories
    ]
    return list(dict.fromkeys([tag for tag in tags if tag]))


class Go(BaseLanguage):
    """Specific actions for a Golang project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return str(get_language_from_file_name(__file__))

    def get_version_tag(self, version: str) -> str:
        """Gets tag based on version."""
        cleansed_version = version.strip().lstrip("v")
        return f"v{cleansed_version}"

    def package_software(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().package_software(mode, version)
        _call_goreleaser_check(version)

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().release_package_to_repository(mode, version)
        self._call_goreleaser_release(version)

    def check_credentials(self) -> None:
        """Checks any credentials."""
        super().check_credentials()
        configuration.get_value(ConfigurationVariable.GIT_TOKEN)

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Generates the code documentation."""
        super().generate_code_documentation(output_directory, module_to_document)
        _call_doc2go(output_directory, module_to_document if module_to_document else "./...")

    def can_add_licence_headers(self) -> bool:
        """States that licence headers can be added."""
        return True

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return False

    def get_secret_registry_exclude_files(self) -> List[str]:
        """Gets additional detect-secrets exclude patterns for Go projects."""
        return [
            r".*go\.sum$",
            r"^\.circleci[\\/].*",
            r"^workflows/.*",
            (r"^\.github[\\/]workflows[\\/].*"),
        ]

    def get_current_spdx_project(self) -> Optional["SpdxProject"]:
        """Gets current SPDX description."""
        # TODO
        return None

    def should_clean_before_packaging(self) -> bool:
        """States whether the repository must be cleaned before packaging happens."""
        return True

    def tag_release(self, git: GitWrapper, version: str, shortcuts: Dict[str, bool]) -> None:
        """Tags release commit."""
        super().tag_release(git, version, shortcuts)
        for go_tag in _determine_go_module_tag(self.get_version_tag(version)):
            git.create_tag(go_tag, message=f"Golang module release: {go_tag}")

    def _call_goreleaser_release(self, version: str) -> None:
        """Calls go releaser release to upload packages."""
        env = os.environ
        env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
        _ensure_go_tool_installed(
            tool_name="syft",
            version_command=["syft", "--version"],
            install_command=_install_syft_command_list(),
            env=env,
        )
        _ensure_go_tool_installed(
            tool_name="goreleaser",
            version_command=["goreleaser", "--version"],
            install_command=_install_goreleaser_command_list(),
            env=env,
        )
        tag = self.get_version_tag(version)
        # The tag of the release must be retrieved
        # See https://github.com/goreleaser/goreleaser/discussions/1426
        logger.info(f"Checking out tag: {tag}.")
        with LocalProjectRepository() as git:
            git.configure_for_github()
            git.fetch()
            git.checkout(f"tags/{tag}")
        logger.info("Release package.")
        changelogPath = configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH)
        env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = tag
        env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
        check_call(
            _generate_goreleaser_release_command_list(changelogPath),
            cwd=ROOT_DIR,
            env=env,
        )
