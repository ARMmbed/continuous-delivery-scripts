#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Retrieves configuration values."""
import argparse
import sys
import logging
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import set_log_level, log_exception

logger = logging.getLogger(__name__)


def main() -> None:
    """Parses command line arguments and retrieves project configuration values."""
    parser = argparse.ArgumentParser(description="Retrieves project configuration values.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--config-variable", help="variable key string", type=str)
    group.add_argument("-k", "--key", help="configuration variable", type=str, choices=ConfigurationVariable.choices())
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        print(configuration.get_value(ConfigurationVariable.parse(args.key) if args.key else args.config_variable))
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
