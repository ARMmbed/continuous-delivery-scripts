#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
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
from license_expression import Licensing
from pathlib import Path
from spdx.utils import SPDXNone, UnKnown
from typing import Union, Optional, Iterator, List

from mbed_tools_ci_scripts.utils.filesystem_helpers import scan_file_for_pattern, should_exclude_path, list_all_files
from mbed_tools_ci_scripts.utils.definitions import UNKNOWN

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
    "**/.egg-info/**",
]


def determine_file_licence(path: Path) -> Optional[str]:
    """Determines the licence of a file based on the SPDX identifier."""
    try:
        match = scan_file_for_pattern(path, SPDX_IDENTIFIER_REGEX_PATTERN)
        if not match:
            return None
        licence = match.group(1).strip()
        return str(Licensing().parse(licence).simplify())
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
    protocol = f"http://"
    path_part = f'{config.get("CreatorWebsite")}/{config.get("PathToSpdx")}'
    name_part = f'{document_name}-{config.get("UUID")}'
    return f"{protocol}{path_part}/{name_part}"


def list_project_files_for_licensing(project_root: Path) -> Iterator[Path]:
    """Gets a generator over all the project's files needing licensing."""

    def ignore_path(p: Path) -> bool:
        return True if p.name.startswith(".") else should_exclude_path(p, PATHS_TO_EXCLUDE)

    return list_all_files(project_root, ignore_path)


def determine_licence_compound(main_licence: str, additional_licences: List[str]) -> str:
    """Determines the overall licence based on main licence and additional licences."""
    overall_licence = f"({main_licence}) AND ({') AND ('.join(additional_licences)})"
    return str(Licensing().parse(overall_licence).simplify())
