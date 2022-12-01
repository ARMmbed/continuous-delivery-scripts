#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers with regards to versioning."""

import logging
import os
from auto_version import auto_version_tool
from typing import Optional, Tuple, Dict

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.filesystem_helpers import cd
from continuous_delivery_scripts.utils.git_helpers import LocalProjectRepository

logger = logging.getLogger(__name__)


def calculate_version(
    commit_type: CommitType, use_news_files: bool, record_state: bool
) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """Calculates the version for the release.

    eg. "0.1.2"

    Args:
        commit_type: release type
        use_news_files: Should the version be dependent on changes recorded in news files

    Returns:
        Tuple containing
            a flag stating whether it is a new version or not
            A semver-style version for the latest release
    """
    BUMP_TYPES = {CommitType.DEVELOPMENT: "build", CommitType.BETA: "prerelease"}
    is_release = commit_type == CommitType.RELEASE
    enable_file_triggers = True if use_news_files else None
    bump = BUMP_TYPES.get(commit_type)
    project_config_path = configuration.get_value(ConfigurationVariable.PROJECT_CONFIG)
    new_version: Optional[str] = None
    is_new_version: bool = False
    with cd(os.path.dirname(project_config_path)):
        old, new_version, updates = auto_version_tool.main(
            release=is_release,
            enable_file_triggers=enable_file_triggers,
            commit_count_as=bump,
            config_path=project_config_path,
            dry_run=not record_state,
        )
        # Autoversion second returned value is not actually the new version
        # There seem to be a bug in autoversion.
        # This is why the following needs to be done to determine the version
        version_elements = _get_version_elements(updates)
        new_version = version_elements.get(auto_version_tool.Constants.VERSION_FIELD, new_version)
        is_new_version = old != new_version
    logger.info(":: Determining the new version")
    logger.info(f"Version: {new_version}")
    return is_new_version, new_version, version_elements


def determine_version_string(
    commit_type: CommitType, new_version: Optional[str], version_elements: Dict[str, str]
) -> Optional[str]:
    """Updates the version string depending on the release type.

    Args:
        commit_type: commit type
        new_version: the new version
        version_elements: version elements
    """
    if commit_type == CommitType.DEVELOPMENT:
        commit_count = version_elements.get(auto_version_tool.Constants.COMMIT_COUNT_FIELD, None)
        if not commit_count:
            with LocalProjectRepository() as git:
                commit_count = git.get_commit_count()
        commit_hash = version_elements.get(auto_version_tool.Constants.COMMIT_FIELD, None)
        if not commit_hash:
            with LocalProjectRepository() as git:
                commit_hash = git.get_commit_hash()
        return "%s-%s.%s+%s" % (
            new_version,
            auto_version_tool.config.BUILD_TOKEN,
            commit_count,
            commit_hash,
        )
    return new_version


def _get_version_elements(native_version_elements: Dict[str, str]) -> Dict[str, str]:
    """Determines the different version elements.

    Args:
        native_version_elements: native version elements as understood by autoversion
    """
    return {
        key: native_version_elements[native]
        for native, key in auto_version_tool.config.key_aliases.items()
        if native in native_version_elements
    }
