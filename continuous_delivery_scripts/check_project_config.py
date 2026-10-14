#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Validate the project's CDS ``[ProjectConfig]`` section."""

import argparse
import logging
import sys

from continuous_delivery_scripts.utils.logging import log_exception, set_log_level
from continuous_delivery_scripts.utils.project_config_schema import validate_project_config

logger = logging.getLogger(__name__)


def main() -> int:
    """Create a CLI for validating the project's CDS configuration."""
    parser = argparse.ArgumentParser(description="Validate CDS ProjectConfig values in pyproject.toml.")
    parser.add_argument("-f", "--config-file", help="Optional path to a pyproject.toml file.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        errors = validate_project_config(args.config_file)
        if errors:
            raise ValueError("Project configuration is invalid:\n- " + "\n- ".join(errors))
        print("Project configuration is valid.")
        return 0
    except Exception as error:
        log_exception(logger, error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
