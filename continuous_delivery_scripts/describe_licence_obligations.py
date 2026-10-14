#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Describe project licence obligations from public SPDX and OSADL sources."""

import argparse
import logging
import sys

from continuous_delivery_scripts.spdx_report.project_licensing import (
    describe_licence_obligations,
)
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def main() -> int:
    """Create a CLI for describing project licence obligations."""
    parser = argparse.ArgumentParser(description="Describe licence obligations from SPDX and OSADL data.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        print(describe_licence_obligations(), end="")
        return 0
    except Exception as error:
        log_exception(logger, error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
