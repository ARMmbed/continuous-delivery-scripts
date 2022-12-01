#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Apply copyright and licensing to all source files present in a project.

This is to comply with OpenChain certification;
https://github.com/OpenChain-Project/Curriculum/blob/master/guides/reusing_software.md#2-include-a-copyright-notice-and-license-in-each-file
"""
import argparse
import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import set_log_level, log_exception
from continuous_delivery_scripts.utils.python.python_helpers import flatten_dictionary
from continuous_delivery_scripts.language_specifics import get_language_specifics
from pathlib import Path

logger = logging.getLogger(__name__)

FILES_TO_IGNORE = ["*.yml", "*.yaml"]
ADDITIONAL_EXTENSIONS = ["python=.toml", "c=.go"]


def insert_licence_header(verbose_count: int) -> None:
    """Inserts a copyright notice at the top of every source file of the current project.

    Wrapper over the [licenseheaders tool](https://github.com/johann-petrak/licenseheaders).
    """
    # copyright (https://github.com/knipknap/copyright) was first considered but
    # comprises quite a few bugs and does not seem active anymore.
    add_licence_header(verbose_count, Path(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))


def add_licence_header(verbose_count: int, src: Path) -> None:
    """Puts a copyright notice at the top of every source file.

    Wrapper over the [licenseheaders tool](https://github.com/johann-petrak/licenseheaders).
    """
    # copyright (https://github.com/knipknap/copyright) was first considered but
    # comprises quite a few bugs and does not seem active anymore.
    if not get_language_specifics().can_add_licence_headers():
        return
    template_string = get_language_specifics().generate_source_licence_header_template()
    with tempfile.NamedTemporaryFile(suffix=".tmpl", delete=False) as template_file:
        template_file_path = Path(template_file.name)
        logger.debug(f"Creates template file in {str(template_file_path)}")
        template_file.write(template_string.encode("utf8"))
        template_file.close()
        copyright_config = get_tool_config(template_file_path, src)
        _call_licensehearders(copyright_config, verbose_count)


def _call_licensehearders(config: dict, verbose_count: int) -> None:
    """Runs licenseheaders tool."""
    args = ["licenseheaders"]
    args_dict = {f"--{k}": v for (k, v) in config.items()}
    args.extend(flatten_dictionary(args_dict))
    if verbose_count > 0:
        args.append(f"-{''.join(['v'] * verbose_count)}")
    subprocess.check_call([str(arg) for arg in args])


def _determines_copyright_dates() -> str:
    """Determines the years the copyright is in use for."""
    this_year = datetime.now().year
    copyright_start_date = configuration.get_value(ConfigurationVariable.COPYRIGHT_START_DATE)
    return _to_copyright_date_string(copyright_start_date, this_year)


def _to_copyright_date_string(start: int, current: int) -> str:
    return f"{current}" if current == start else f"{start}-{current}"


def get_tool_config(template_file: Path, src: Path) -> dict:
    """Gets the configuration for licenseheaders."""
    copyright_dates = _determines_copyright_dates()
    return {
        "owner": configuration.get_value(ConfigurationVariable.ORGANISATION),
        "dir": src,
        "projname": configuration.get_value(ConfigurationVariable.PROJECT_NAME),
        "tmpl": str(template_file),
        "years": copyright_dates,
        "additional-extensions": ADDITIONAL_EXTENSIONS,
        "exclude": FILES_TO_IGNORE,
    }


def main() -> int:
    """Creates a CLI."""
    parser = argparse.ArgumentParser(description="Adds licence header to every source file of a project.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        insert_licence_header(args.verbose)
    except Exception as e:
        log_exception(logger, e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
