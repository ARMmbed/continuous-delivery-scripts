#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Facilities regarding SPDX.

SPDX file (i.e. tag-value format)
https://github.com/OpenChain-Project/curriculum/blob/master/guides/including_license_info.rst
https://github.com/david-a-wheeler/spdx-tutorial#spdx-files
https://github.com/OpenChain-Project/curriculum/blob/master/guides/reusing_software.md
https://github.com/vmware/tern/blob/c9a0c83369b92df58f7f80842aa15da5f63ed983/docs/spdx-tag-value-overview.md
Examples:
    - https://spdx.org/spdx-tagvalue-example
    - https://github.com/spdx/tools/blob/master/Examples/SPDXTagExample-v2.1.spdx
"""
import re

import logging
import toml
from pathlib import Path
from spdx.utils import SPDXNone, UnKnown
from typing import Union, Optional, Iterator, Any, Tuple

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.definitions import UNKNOWN
from continuous_delivery_scripts.utils.filesystem_helpers import (
    scan_file_for_pattern,
    should_exclude_path,
    list_all_files,
)
from continuous_delivery_scripts.utils.third_party_licences import simplify_licence_expression

logger = logging.getLogger(__name__)

# Copyright similar to the regex defined in flake8-copyright
COPYRIGHT_PATTERN = r"((?i)Copyright(?i).*$)"
COPYRIGHT_REGEX_PATTERN = re.compile(COPYRIGHT_PATTERN, re.MULTILINE)
# Specification of the identifier based on https://spdx.org/spdx-specification-21-web-version#h.twlc0ztnng3b
# and https://spdx.org/ids-how
SPDX_LICENCE_IDENTIFIER_PATTERN = r"SPDX-License-Identifier: ([\.\w+\-\(\)\s]+)[\*]?$"
SPDX_IDENTIFIER_REGEX_PATTERN = re.compile(SPDX_LICENCE_IDENTIFIER_PATTERN, re.MULTILINE)
THIRD_PARTY_CONFIG_NAMESPACE = "spdx"
PATHS_TO_EXCLUDE = [
    "*.spdx",
    "*.png",
    "*.jpg",
    "*.rdf",
    "*.pyc",
    "*.bin",
    "*.tar",
    "*.zip",
    "**/__pycache__/**",
    "**/*.egg-info/**",
]


def determine_file_licence(path: Path) -> Optional[str]:
    """Determines the licence of a file based on the SPDX identifier."""
    licence = None
    try:
        match = scan_file_for_pattern(path, SPDX_IDENTIFIER_REGEX_PATTERN)
        if not match:
            return None
        licence = match.group(1).strip()
        return simplify_licence_expression(licence)
    except Exception as e:
        logger.error(f"Could not determine the licence of file [{path}] from identifier '{licence}'. Reason: {e}.")
        return None


def determine_file_copyright_text(path: Path) -> Optional[str]:
    """Determines the copyright text of a file."""
    match = scan_file_for_pattern(path, COPYRIGHT_REGEX_PATTERN)
    if not match:
        return None
    return str(match.group(1).strip())


def determine_spdx_value(value: Optional[str]) -> Union[str, UnKnown, SPDXNone]:
    """Determines the correct SPDX value.

    Args:
        value: a value
    Returns:
        correct SPDX value a string, UnKnown or SPDXNone
    """
    if not value:
        return SPDXNone()
    if value == UNKNOWN:
        return UnKnown()

    return value


def get_project_namespace(project_config_path: Path, document_name: str) -> str:
    """Determines the project namespace from configuration."""
    with open(str(project_config_path), "r", encoding="utf8") as f:
        config = toml.load(f).get(THIRD_PARTY_CONFIG_NAMESPACE, dict())
    protocol = "http://"
    path_part = f'{config.get("CreatorWebsite")}/{config.get("PathToSpdx")}'
    name_part = f'{document_name}-{config.get("UUID")}'
    return f"{protocol}{path_part}/{name_part}"


def list_project_files_for_licensing(project_root: Path) -> Iterator[Path]:
    """Gets a generator over all the project's files needing licensing."""

    def ignore_path(p: Path) -> bool:
        return True if p.name.startswith(".") else should_exclude_path(p, PATHS_TO_EXCLUDE)

    return list_all_files(project_root, ignore_path)


def _convert_list_into_dict(checked_packages: Any) -> dict:
    checked_package_description = dict()
    for item in checked_packages:
        info = item.split("=" if "=" in item else ":")
        checked_package_description[info[0].strip()] = info[-1].strip() if len(info) > 1 else None
    return checked_package_description


def determine_checked_packages_from_configuration_entry(checked_packages: Any) -> dict:
    """Determines the list of packages for which the licence has been manually checked."""
    if isinstance(checked_packages, str):
        checked_packages = checked_packages.split(", ")
    if isinstance(checked_packages, (list, tuple, set)):
        return _convert_list_into_dict(checked_packages)
    if isinstance(checked_packages, dict):
        return checked_packages
    return dict()


def get_packages_with_checked_licence() -> dict:
    """Determines the list of packages for which the licence has been checked from configuration."""
    return determine_checked_packages_from_configuration_entry(
        configuration.get_value(ConfigurationVariable.PACKAGES_WITH_CHECKED_LICENCE)
    )


def get_package_manual_check(package_name: str) -> Tuple[bool, Optional[str]]:
    """Gets information about package licence manual check."""
    checked_packages = get_packages_with_checked_licence()
    return bool(package_name.strip() in checked_packages), checked_packages.get(package_name.strip())


def is_package_licence_manually_checked(package_name: str) -> bool:
    """States whether the licence of a package has been manually checked and hence, that its licence is compliant."""
    checked, _ = get_package_manual_check(package_name)
    if not checked:
        checked, _ = get_package_manual_check(package_name.replace(".", "-"))
    return checked
