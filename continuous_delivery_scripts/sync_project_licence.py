#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Ensure the configured top-level licence file exists and matches project configuration."""

import argparse
import logging
import sys

from continuous_delivery_scripts.spdx_report.project_licensing import (
    sync_project_licence_file,
)
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def main() -> int:
    """Create a CLI for syncing the project's top-level licence file."""
    parser = argparse.ArgumentParser(
        description=(
            "Create the configured project licence file when it is missing and check it matches "
            "the configured SPDX identifier."
        )
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        licence_file = sync_project_licence_file()
        if licence_file.exists():
            print(f"Project licence file matches configured SPDX identifier: {licence_file}")
        return 0
    except Exception as error:
        log_exception(logger, error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
