#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Record the project's accepted secret registry using detect-secrets."""

import argparse
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)

GENERIC_SECRET_REGISTRY_EXCLUDE_FILES = [
    r".*\.html$",
    r".*\.properties$",
    r".*ci\.yml$",
    r"^\.git[\\/]",
]


def _get_secrets_baseline_filename() -> str:
    return str(configuration.get_value(ConfigurationVariable.SECRETS_BASELINE_FILENAME))


def _get_secrets_baseline_file(output_file: Optional[Path] = None) -> Path:
    project_root = Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))
    baseline_file = output_file or Path(_get_secrets_baseline_filename())
    return baseline_file if baseline_file.is_absolute() else project_root.joinpath(baseline_file)


def _generate_detect_secrets_command_list(exclude_files: List[str]) -> List[str]:
    command = ["detect-secrets", "scan", "--all-files"]
    for exclude_file in exclude_files:
        command.extend(["--exclude-files", exclude_file])
    return command


def _determine_exclude_files() -> List[str]:
    exclude_files = list(GENERIC_SECRET_REGISTRY_EXCLUDE_FILES)
    baseline_file_pattern = re.escape(_get_secrets_baseline_filename()).replace(r"\\", r"[\\/]")
    exclude_files.append(rf"^{baseline_file_pattern}$")
    exclude_files.extend(get_language_specifics().get_secret_registry_exclude_files())
    return list(dict.fromkeys(exclude_files))


def update_secrets_registry(output_file: Optional[Path] = None) -> Path:
    """Record the project's accepted secret registry for detect-secrets."""
    project_root = Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))
    baseline_file = _get_secrets_baseline_file(output_file)
    logger.info("Updating secrets baseline at [%s].", baseline_file)
    baseline_contents = subprocess.check_output(
        _generate_detect_secrets_command_list(_determine_exclude_files()),
        cwd=str(project_root),
        encoding="utf8",
    )
    baseline_file.write_text(baseline_contents, encoding="utf8")
    return baseline_file


def main() -> int:
    """Script CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Record the project's accepted secret registry so allowed findings are not flagged again. "
            "This uses Yelp detect-secrets (https://github.com/Yelp/detect-secrets)."
        )
    )
    parser.add_argument(
        "-r",
        "--registry-file",
        default=_get_secrets_baseline_filename(),
        help="Secret registry file to generate.",
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
        update_secrets_registry(args.registry_file)
        return 0
    except Exception as e:
        log_exception(logger, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
