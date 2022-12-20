#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Determine the project new version."""
import sys

import argparse
import logging
from continuous_delivery_scripts.utils.versioning import calculate_version, determine_version_string

from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def get_project_version_string(commit_type: CommitType) -> str:
    """Determine the project version string.

    Args:
        commit_type: states what is the type of the commit


    Returns:
        (is new version, the new version)
    """
    use_news_files = commit_type in [CommitType.BETA, CommitType.RELEASE]
    _, new_version, version_elements = calculate_version(commit_type, use_news_files, False)
    version_string = determine_version_string(commit_type, new_version, version_elements)
    return version_string


def main() -> None:
    """Handle command line arguments to determine version string."""
    parser = argparse.ArgumentParser(description="Determine project's new version.")
    parser.add_argument(
        "-t", "--release-type", help="type of release to perform", required=True, type=str, choices=CommitType.choices()
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        commit_type = CommitType.parse(args.release_type)
        version_to_print = get_project_version_string(commit_type)
        print(version_to_print)
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
