#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Check project and dependency licences without generating SPDX documents."""

import argparse
import logging
import sys
from pathlib import Path

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.spdx_report.licence_assessment import LicenceAssessment
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def main() -> int:
    """Check licence compliance and optionally write third-party IP summaries."""
    parser = argparse.ArgumentParser(description="Check project and dependency licence compliance.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Write third-party IP summaries to this existing directory (no SPDX documents).",
    )
    parser.add_argument(
        "--lookup-scancode",
        action="store_true",
        help="Consult ScanCode LicenseDB for unclassified licences or missing assessment rules.",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        plugin = get_language_specifics()
        if not plugin.can_get_project_metadata():
            raise ValueError("The selected language plugin cannot provide metadata for licence compliance checks.")
        project = plugin.get_current_spdx_project()
        if project is None:
            raise ValueError("The selected language plugin did not return a project for licence compliance checks.")
        if args.lookup_scancode:
            project.enable_scancode_lookup()
        if args.output_dir is not None:
            project.generate_licensing_summary(args.output_dir)
        counts = {
            status.value: sum(result.status is status for result in project.licence_assessments.values())
            for status in LicenceAssessment
        }
        print("Dependency licence assessment: " + ", ".join(f"{name}: {count}" for name, count in counts.items()))
        if args.lookup_scancode:
            for name, result in project.licence_assessments.items():
                for info in result.scancode_licences:
                    print(f"{name}: ScanCode LicenseDB: {info.identifier} ({info.category}): {info.url}")
        project.check_licence_compliance()
        if args.lookup_scancode:
            for warning in project.scancode_follow_up_warnings():
                print(f"WARNING: {warning}", file=sys.stderr)
        return 0
    except Exception as error:
        log_exception(logger, error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
