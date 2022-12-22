#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for CI projects."""
import logging
import os
from pathlib import Path
from subprocess import check_call
from typing import List

from continuous_delivery_scripts.plugins.ci import CI
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.language_specifics_base import get_language_from_file_name

logger = logging.getLogger(__name__)
ENVVAR_GITHUB_CLI_GIT_TOKEN = "GITHUB_TOKEN"


def _generate_github_cli_release_command_list(
    changelog: Path, version: str, tag: str, is_latest: bool, is_prerelease: bool
) -> List[str]:
    cmd = [
        "gh",
        "release",
        "create",
        f"{tag}",
        "--notes-file",
        f"{str(changelog)}",
    ]
    title = f"Release {version}"
    if is_latest:
        cmd.append("--latest")
    if is_prerelease:
        cmd.append("--prerelease")
        title = f"Pre-release {version}"
    cmd.append("--title")
    cmd.append(title)
    return cmd


def _generate_github_cli_check_command_list() -> List[str]:
    return [
        "gh",
        "--version",
    ]


def _call_github_cli_check() -> None:
    """Calls gh to verify its accessibility."""
    logger.info("Checking whether GitHub CLI is correctly installed.")
    env = os.environ
    env[ENVVAR_GITHUB_CLI_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_github_cli_check_command_list(), env=env)


class GitHubActions(CI):
    """Specific actions for a GitHub Action project."""

    def package_software(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().package_software(mode, version)
        _call_github_cli_check()

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().release_package_to_repository(mode, version)
        is_latest = mode == CommitType.RELEASE
        is_prerelease = mode == CommitType.BETA
        self._call_github_cli_release(version, is_latest, is_prerelease)

    def _call_github_cli_release(self, version: str, is_latest: bool, is_prerelease: bool) -> None:
        """Calls github cli to create a release."""
        tag = self.get_version_tag(version)
        logger.info(f"Create a GitHub Release {version}")
        changelogPath = configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH)
        env = os.environ
        env[ENVVAR_GITHUB_CLI_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)

        check_call(
            _generate_github_cli_release_command_list(changelogPath, version, tag, is_latest, is_prerelease), env=env
        )
