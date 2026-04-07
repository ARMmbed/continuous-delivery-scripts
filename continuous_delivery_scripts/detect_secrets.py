#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Check tracked files against the project's recorded secret registry."""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from continuous_delivery_scripts.update_secrets_registry import (
    _determine_exclude_files,
    _get_secrets_baseline_file,
    _get_secrets_baseline_filename,
)
from continuous_delivery_scripts.utils.git_helpers import ProjectGitWrapper
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)


def _generate_detect_secrets_hook_command_list(
    baseline_file: Path, exclude_files: List[str], tracked_files: List[str]
) -> List[str]:
    command = ["detect-secrets-hook", "--baseline", str(baseline_file)]
    for exclude_file in exclude_files:
        command.extend(["--exclude-files", exclude_file])
    command.extend(tracked_files)
    return command


def _filter_tracked_files(tracked_files: List[str], project_root: Path, registry_file: Path) -> List[str]:
    """Remove the registry file from tracked files to avoid scanning recorded accepted findings."""
    try:
        registry_relative_path = registry_file.relative_to(project_root).as_posix()
    except ValueError:
        return tracked_files
    return [path for path in tracked_files if path != registry_relative_path]


def detect_secrets(baseline_file: Optional[Path] = None) -> None:
    """Check tracked files so new secrets are not introduced."""
    git = ProjectGitWrapper()
    project_root = Path(str(git.root))
    resolved_baseline = _get_secrets_baseline_file(baseline_file)
    tracked_files = _filter_tracked_files(git.list_tracked_files(), project_root, resolved_baseline)
    if not tracked_files:
        logger.info("No tracked files found for detect-secrets.")
        return
    subprocess.check_call(
        _generate_detect_secrets_hook_command_list(resolved_baseline, _determine_exclude_files(), tracked_files),
        cwd=str(project_root),
    )


def main() -> int:
    """Script CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Check tracked files against the recorded secret registry so new secrets are not committed. "
            "This uses Yelp detect-secrets (https://github.com/Yelp/detect-secrets)."
        )
    )
    parser.add_argument(
        "-r",
        "--registry-file",
        default=Path(_get_secrets_baseline_filename()),
        help="Secret registry file to use.",
        type=Path,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity, by default errors are reported.",
    )
    args = parser.parse_args()
    set_log_level(args.verbose)

    try:
        detect_secrets(args.registry_file)
        return 0
    except Exception as e:
        log_exception(logger, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
