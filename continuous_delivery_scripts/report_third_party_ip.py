#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Script providing information about licensing and third party IP in order to comply with OpenChain.

The current script uses the SDK provided by the SPDX organisation
(i.e. https://github.com/spdx/tools-python).
This SDK only supports version 1.2 of the specification and not 2.1.
Therefore, some changes will have to be carried out when the later version is
supported so that third-party IP gets documented as described by the
specification (i.e. with relationships).
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.logging import set_log_level, log_exception

logger = logging.getLogger(__name__)


def generate_spdx_project_reports(project: SpdxProject, output_directory: Path) -> SpdxProject:
    """Generates all the SPDX reports for a given project."""
    logger.info("Generating SPDX report.")
    project.generate_tag_value_files(output_directory)
    logger.info("Generating licensing summary.")
    project.generate_licensing_summary(output_directory)
    return project


def generate_spdx_reports(output_directory: Path) -> Optional[SpdxProject]:
    """Generates all the SPDX reports for the current project."""
    project = get_language_specifics().get_current_spdx_project()
    if not project:
        return None
    return generate_spdx_project_reports(project, output_directory)


def main() -> int:
    """Script CLI."""
    parser = argparse.ArgumentParser(description="Generate licence and third-party IP reports.")

    def convert_to_path(arg: Any) -> Path:
        """Converts argument to a path."""
        return Path(arg)

    parser.add_argument(
        "-o", "--output-dir", help="Output directory where the files are generated", required=True, type=convert_to_path
    )

    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        if get_language_specifics().can_get_project_metadata():
            project = generate_spdx_reports(args.output_dir)
            if project:
                project.check_licence_compliance()
        return 0
    except Exception as e:
        log_exception(logger, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
