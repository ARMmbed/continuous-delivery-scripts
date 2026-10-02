#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Check project and dependency licences without generating SPDX documents."""

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.spdx_report.licence_assessment import LicenceAssessment
from continuous_delivery_scripts.spdx_report.spdx_summary import _configured_licence_policy
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

if TYPE_CHECKING:
    from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject

logger = logging.getLogger(__name__)


def _log_assessment_details(project: "SpdxProject") -> None:
    """Log per-dependency assessment details for statuses that need attention."""
    if not logger.isEnabledFor(logging.WARNING):
        return
    attention = [
        (name, result)
        for name, result in sorted(project.licence_assessments.items())
        if result.status in (LicenceAssessment.REVIEW, LicenceAssessment.UNKNOWN, LicenceAssessment.DENY)
    ]
    if not attention:
        return
    logger.warning("Dependencies needing attention:")
    for name, result in attention:
        discovered = result.discovered_licence or result.dependency_licence
        details = [
            f"status={result.status.value}",
            f"discovered_licence={discovered}",
            f"assessed_licence={result.dependency_licence}",
            f"rule={result.rule}",
            f"reason={result.reason}",
        ]
        if result.selected_licence:
            details.append(f"selected_licence={result.selected_licence}")
        logger.warning("- %s: %s", name, "; ".join(details))


def _print_policy_summary(project: "SpdxProject") -> None:
    """Print a human-readable summary of the configured licence policy and outcome."""
    counts = {
        status.value: sum(result.status is status for result in project.licence_assessments.values())
        for status in LicenceAssessment
    }
    accepted = _configured_licence_policy()
    fail_on = sorted(status.value for status in project.licence_assessor.policy.fail_on)
    fail_on_incomplete = bool(configuration.get_value(ConfigurationVariable.FAIL_ON_INCOMPLETE_LICENCE_AUDIT))
    dependency_count = len(project.dependency_documents)
    policy_result = "PASS"
    policy_error = None
    try:
        project.check_licence_compliance()
    except Exception as error:
        policy_result = "FAIL"
        policy_error = error

    print(f"Dependencies screened: {dependency_count}")
    print("Accepted third-party licences: " + (", ".join(accepted) if accepted else "<none configured>"))
    print("Assessment fail-on statuses: " + (", ".join(fail_on) if fail_on else "<disabled>"))
    print(f"Fail on incomplete licence audit: {'enabled' if fail_on_incomplete else 'disabled'}")
    print("Dependency licence assessment: " + ", ".join(f"{name}: {count}" for name, count in counts.items()))
    print(f"Compliance with configured licence policy: {policy_result}")
    if policy_error:
        raise policy_error


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
    parser.add_argument(
        "--skip-dependency-download",
        action="store_true",
        help="Skip automatic dependency downloads before licence checks and SPDX dependency analysis.",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        plugin = get_language_specifics()
        if not plugin.can_get_project_metadata():
            raise ValueError("The selected language plugin cannot provide metadata for licence compliance checks.")
        project = plugin.get_current_spdx_project(skip_dependency_download=args.skip_dependency_download)
        if project is None:
            raise ValueError("The selected language plugin did not return a project for licence compliance checks.")
        if args.lookup_scancode:
            project.enable_scancode_lookup()
        if args.output_dir is not None:
            project.generate_licensing_summary(args.output_dir)
        _print_policy_summary(project)
        _log_assessment_details(project)
        if args.lookup_scancode:
            for name, result in project.licence_assessments.items():
                for info in result.scancode_licences:
                    print(f"{name}: ScanCode LicenseDB: {info.identifier} ({info.category}): {info.url}")
        if args.lookup_scancode:
            for warning in project.scancode_follow_up_warnings():
                print(f"WARNING: {warning}", file=sys.stderr)
        return 0
    except Exception as error:
        log_exception(logger, error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
