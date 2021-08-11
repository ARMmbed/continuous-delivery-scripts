#
# Copyright (C) 2020-2021 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Golang projects."""
import logging
import os
from pathlib import Path
from typing import Optional, List
from subprocess import check_call
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name
from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable

logger = logging.getLogger(__name__)

SRC_DIR = configuration.get_value(ConfigurationVariable.SOURCE_DIR)
ENVVAR_GORELEASER_GIT_TOKEN = "GITHUB_TOKEN"
ENVVAR_GORELEASER_CUSTOMISED_TAG = "GORELEASER_CURRENT_TAG"


def _generate_golds_command_list(output_directory: Path, module: str) -> List[str]:
    return ["golds", "-gen", "-wdpkgs-listing=promoted", f"-dir={str(output_directory)}", "-nouses", f"{module}"]


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
    return ["go", "install", "go101.org/golds@latest"]


def _install_goreleaser_command_list() -> List[str]:
    return ["go", "install", "github.com/goreleaser/goreleaser@latest"]


def _call_golds(output_directory: Path, module: str) -> None:
    """Calls Golds for generating the docs."""
    logger.info("Installing Golds if missing.")
    check_call(_install_golds_command_list())
    logger.info("Creating Golds documentation.")
    check_call(_generate_golds_command_list(output_directory, module), cwd=SRC_DIR)


def _call_goreleaser_check(version: str) -> None:
    """Calls go releaser check to verify configuration."""
    logger.info("Installing GoReleaser if missing.")
    check_call(_install_goreleaser_command_list())
    logger.info("Checking GoReleaser configuration.")
    env = os.environ
    env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = version
    env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_goreleaser_check_command_list(), cwd=SRC_DIR)


def _call_goreleaser_release(version: str) -> None:
    """Calls go releaser release to upload packages."""
    logger.info("Installing GoReleaser if missing.")
    check_call(_install_goreleaser_command_list())
    logger.info("Release package.")
    changelogPath = configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH)
    env = os.environ
    env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = version
    env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_goreleaser_release_command_list(changelogPath), cwd=SRC_DIR, env=env)


class Go(BaseLanguage):
    """Specific actions for a Golang project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def get_version_tag(self, version: str):
        """Gets tag based on version."""
        cleansed_version = version.strip().lstrip("v")
        return f"v{cleansed_version}"

    def package_software(self, version: str) -> None:
        """No operation."""
        super().package_software(version)
        _call_goreleaser_check(version)

    def release_package_to_repository(self, version: str) -> None:
        """No operation."""
        super().release_package_to_repository(version)
        _call_goreleaser_release(version)

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
