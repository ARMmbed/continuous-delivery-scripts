#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Handles usage of towncrier for automated changelog generation and pyautoversion for versioning."""
import sys

import argparse
import logging
import os
import subprocess
from continuous_delivery_scripts.utils.versioning import calculate_version, determine_version_string
from typing import Optional, Tuple, Dict

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.filesystem_helpers import cd
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def version_project(commit_type: CommitType) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """Versions the project.

    Args:
        commit_type: states what is the type of the commit


    Returns:
        (is new version, the new version)
    """
    use_news_files = commit_type in [CommitType.BETA, CommitType.RELEASE]
    is_new_version, new_version, version_elements = calculate_version(commit_type, use_news_files, True)
    _generate_changelog(new_version, use_news_files)
    return is_new_version, new_version, version_elements


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
            subprocess.check_call(["towncrier", "build", "--yes", '--name=""', f'--version="{version}"'])


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
        version_to_print = determine_version_string(commit_type, new_version, version_elements)
        print(version_to_print)
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
