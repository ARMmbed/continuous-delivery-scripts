#
# Copyright (C) 2020-2021 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Handles usage of towncrier for automated changelog generation and pyautoversion for versioning."""
import sys

import argparse
import logging
import os
import subprocess
from auto_version import auto_version_tool
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import LocalProjectRepository
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level
from continuous_delivery_scripts.utils.filesystem_helpers import cd
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)


def version_project(commit_type: CommitType) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """Versions the project.

    Args:
        commit_type: states what is the type of the commit


    Returns:
        (is new version, the new version)
    """
    use_news_files = commit_type in [CommitType.BETA, CommitType.RELEASE]
    is_new_version, new_version, version_elements = _calculate_version(commit_type, use_news_files)
    _generate_changelog(new_version, use_news_files)
    return is_new_version, new_version, version_elements


def _calculate_version(commit_type: CommitType, use_news_files: bool) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """Calculates the version for the release.

    eg. "0.1.2"

    Args:
        commit_type:
        use_news_files: Should the version be dependant on changes recorded in news files

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


def _update_version_string(
    commit_type: CommitType, new_version: Optional[str], version_elements: Dict[str, str]
) -> Optional[str]:
    """Updates the version string for development releases.

    Args:
        commit_type: commit type
        new_version: the new version
        version_elements: version elements
    """
    if commit_type == CommitType.DEVELOPMENT:
        commit_count = version_elements.get(auto_version_tool.Constants.COMMIT_COUNT_FIELD)
        if not commit_count:
            with LocalProjectRepository() as git:
                commit_count = git.get_commit_count()
        return "%s-%s.%s+%s" % (
            new_version,
            auto_version_tool.config.BUILD_TOKEN,
            commit_count,
            version_elements.get(auto_version_tool.Constants.COMMIT_FIELD),
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


def _generate_changelog(version: Optional[str], use_news_files: bool) -> None:
    """Creates a towncrier log of the release.

    Will only create a log entry if we are using news files.

    Args:
        version: the semver version of the release
        use_news_files: are we generating the release from news files
    """
    if use_news_files:
        logger.info(":: Generating a new changelog")
        project_config_path = configuration.get_value(ConfigurationVariable.PROJECT_CONFIG)
        with cd(os.path.dirname(project_config_path)):
            subprocess.check_call(["towncrier", "--yes", '--name=""', f'--version="{version}"'])


def main() -> None:
    """Handle command line arguments to generate a version and changelog file."""
    parser = argparse.ArgumentParser(description="Versions the project.")
    parser.add_argument(
        "-t", "--release-type", help="type of release to perform", required=True, type=str, choices=CommitType.choices()
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        commit_type = CommitType.parse(args.release_type)
        is_new_version, new_version, version_elements = version_project(commit_type)
        version_to_print = _update_version_string(commit_type, new_version, version_elements)
        print(version_to_print)
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
