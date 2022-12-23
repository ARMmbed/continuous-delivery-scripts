#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Golang projects."""
import logging
import os
from pathlib import Path
from subprocess import check_call
from typing import Optional, List, Dict

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import LocalProjectRepository, GitWrapper
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name

logger = logging.getLogger(__name__)

SRC_DIR = Path(str(configuration.get_value(ConfigurationVariable.SOURCE_DIR)))
ROOT_DIR = Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))
ENVVAR_GORELEASER_GIT_TOKEN = "GITHUB_TOKEN"
ENVVAR_GORELEASER_CUSTOMISED_TAG = "GORELEASER_CURRENT_TAG"
ENVVAR_GO_MOD = "GO111MODULE"
GO_MOD_ON_VALUE = "on"


def _generate_golds_command_list(output_directory: Path, module: str) -> List[str]:
    return [
        "golds",
        "-gen",
        "-wdpkgs-listing=solo",
        "-only-list-exporteds",
        f"-dir={str(output_directory)}",
        "-nouses",
        f"{module}",
    ]


def _generate_goreleaser_release_command_list(changelog: Path) -> List[str]:
    return [
        "goreleaser",
        "release",
        "--rm-dist",
        "--release-notes",
        f"{str(changelog)}",
    ]


def _generate_goreleaser_check_command_list() -> List[str]:
    return [
        "goreleaser",
        "check",
    ]


def _install_golds_command_list() -> List[str]:
    return [
        "go",
        "install",
        "go101.org/golds@main",
    ]  # FIXME change version to latest when https://github.com/go101/golds/issues/26 is fixed


def _install_goreleaser_command_list() -> List[str]:
    return ["go", "install", "github.com/goreleaser/goreleaser@latest"]


def _call_golds(output_directory: Path, module: str) -> None:
    """Calls Golds for generating the docs."""
    logger.info("Installing Golds if missing.")
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    check_call(_install_golds_command_list(), env=env)
    logger.info("Creating Code documentation.")
    logger.info(f"Running Golds over [{module}] in [{SRC_DIR}].")
    # check_call(_generate_golds_command_list(output_directory, module), cwd=str(SRC_DIR), env=env)
    # FIXME
    logger.warning(
        "Currently not running golds because there is an issue with latest versions: "
        + "https://github.com/go101/golds/issues/26"
    )


def _call_goreleaser_check(version: str) -> None:
    """Calls go releaser check to verify configuration."""
    logger.info("Installing GoReleaser if missing.")
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    check_call(_install_goreleaser_command_list(), env=env)
    logger.info("Checking GoReleaser configuration.")
    env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = version
    env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_goreleaser_check_command_list(), cwd=ROOT_DIR, env=env)


def _determine_go_module_tag(version) -> Optional[str]:
    """Determines go module for tagging.

    See https://golang.org/ref/mod#vcs-version.
    and https://github.com/golang/go/wiki/Modules#should-i-have-multiple-modules-in-a-single-repository.
    """
    module = ""
    try:
        module = str(SRC_DIR.relative_to(ROOT_DIR))
    except ValueError:
        try:
            module = str(ROOT_DIR.relative_to(SRC_DIR))
        except ValueError as exception:
            logger.warning(exception)
    if module == "." or len(module) == 0:
        return None
    module = module.rstrip("/")
    return f"{module}/{version}"


class Go(BaseLanguage):
    """Specific actions for a Golang project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def get_version_tag(self, version: str):
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
        _call_golds(output_directory, "./...")

    def can_add_licence_headers(self) -> bool:
        """States that licence headers can be added."""
        return True

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return False

    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """Gets current SPDX description."""
        # TODO
        return None

    def should_clean_before_packaging(self) -> bool:
        """States whether the repository must be cleaned before packaging happens."""
        return True

    def tag_release(self, git: GitWrapper, version: str, shortcuts: Dict[str, bool]) -> None:
        """Tags release commit."""
        super().tag_release(git, version, shortcuts)
        go_tag = _determine_go_module_tag(self.get_version_tag(version))
        if go_tag:
            git.create_tag(go_tag, message=f"Golang module release: {go_tag}")

    def _call_goreleaser_release(self, version: str) -> None:
        """Calls go releaser release to upload packages."""
        logger.info("Installing GoReleaser if missing.")
        env = os.environ
        env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
        check_call(_install_goreleaser_command_list(), env=env)
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
        check_call(_generate_goreleaser_release_command_list(changelogPath), cwd=ROOT_DIR, env=env)
