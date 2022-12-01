#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving Python's package information."""

import logging
import re
import subprocess
import sys
from typing import List, Any, cast

import pkg_resources

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.package_helpers import ProjectMetadataFetcher, PackageMetadata, ProjectMetadata

logger = logging.getLogger(__name__)


class PythonProjectMetadataFetcher(ProjectMetadataFetcher):
    """Parser of python package metadata."""

    ENTRY_PATTERN = r"^([^:]*):(.*)$"

    def __init__(self, package_name: str) -> None:
        """Initialiser."""
        super().__init__(package_name)

    def fetch_project_metadata(self) -> ProjectMetadata:
        """Parses package metadata."""
        project_metadata = ProjectMetadata(self._package_name)
        for metadata in get_all_packages_metadata_lines(self._package_name):
            info = parse_package_metadata_lines(metadata)
            if info.name == self._package_name:
                project_metadata.project_metadata = info
            else:
                project_metadata.add_dependency_metadata(info)
        return project_metadata


class CurrentPythonProjectMetadataFetcher(PythonProjectMetadataFetcher):
    """Fetches the current python project metadata."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__(configuration.get_value(ConfigurationVariable.PACKAGE_NAME))


def get_package_metadata_lines(package: Any) -> list:
    """Determines the metadata lines of a package.

    Depending on the package, there may be a METADATA or a PKG-INFO file.
    We need to try both to get the metadata lines and
    the underlying `get_metadata_lines` function used raises an exception if the file does not exist.
    We hence need to try to catch all exceptions
    """
    try:
        return cast(list, package.get_metadata_lines("METADATA"))
    except Exception as e:
        logger.warning(e)
    try:
        return cast(list, package.get_metadata_lines("PKG-INFO"))
    except Exception as e:
        logger.warning(e)
    return list()


def get_all_packages_metadata_lines(package_name: str) -> List[list]:
    """Determines the metadata lines for the present package as well as for all its dependencies."""
    return [get_package_metadata_lines(package) for package in pkg_resources.require(package_name)]


def parse_package_metadata_lines(metadata: list) -> PackageMetadata:
    """Parses package metadata lines and retains relevant information."""
    metadata_dict = dict()
    for line in metadata:
        match = re.search(CurrentPythonProjectMetadataFetcher.ENTRY_PATTERN, line)
        if match:
            metadata_dict[match.group(1).strip()] = match.group(2).strip()
    return PackageMetadata(metadata_dict)


def generate_package_info() -> None:
    """Generates package information (egg)."""
    command = [sys.executable, "setup.py", "develop", "-v"]
    subprocess.check_call(command, cwd=configuration.get_value(ConfigurationVariable.PROJECT_ROOT))
