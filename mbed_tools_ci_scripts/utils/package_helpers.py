#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving Python's package information."""

import logging
import re
from typing import List, Any, Optional, cast

import pkg_resources

from mbed_tools_ci_scripts.utils.configuration import (
    ConfigurationVariable,
    configuration,
)
from .definitions import UNKNOWN
import sys
import subprocess

logger = logging.getLogger(__name__)


class PackageMetadata:
    """Package's metadata.

    Retrieves all the information it needs from Python's metadata dictionary.
    It is based on https://www.python.org/dev/peps/pep-0314/
    https://packaging.python.org/specifications/core-metadata/
    """

    def __init__(self, data: dict) -> None:
        """Constructor."""
        self._data = data

    @property
    def name(self) -> str:
        """Gets package's name."""
        return self._data.get("Name", UNKNOWN)

    @property
    def version(self) -> str:
        """Gets package's version."""
        return self._data.get("Version", UNKNOWN)

    @property
    def author(self) -> str:
        """Gets package's author."""
        return self._data.get("Author", UNKNOWN)

    @property
    def author_email(self) -> str:
        """Gets package's author email."""
        return self._data.get("Author-email", UNKNOWN)

    @property
    def licence(self) -> str:
        """Gets package's licence."""
        return self._data.get("License", UNKNOWN)

    @property
    def description(self) -> str:
        """Gets package's licence."""
        return self._data.get("Summary", UNKNOWN)

    @property
    def url(self) -> str:
        """Gets package's URL."""
        home_page = str(self._data.get("Home-page"))
        if home_page:
            return home_page
        url = str(self._data.get("Project-URL"))
        if url:
            return url.split(",")[1].strip()
        return UNKNOWN

    def __str__(self) -> str:
        """String representation."""
        relevant_data = [
            f"{getter}: {getattr(self, getter, None)}" for getter in dir(self) if not getter.startswith("_") and getter
        ]
        return ", ".join(relevant_data)


class ProjectMetadata:
    """Metadata for a project."""

    def __init__(self, package_name: str) -> None:
        """Constructor."""
        self._package_metadata: PackageMetadata = PackageMetadata(dict())
        self._dependency_packages_metadata: List[PackageMetadata] = list()
        self._package_name: str = package_name

    @property
    def dependencies_metadata(self) -> List[PackageMetadata]:
        """Gets all package's dependencies metadata."""
        return self._dependency_packages_metadata

    @property
    def project_metadata(self) -> PackageMetadata:
        """Gets project metadata."""
        return self._package_metadata

    @property
    def package_name(self) -> str:
        """Gets project's package name."""
        return self._package_name

    def __str__(self) -> str:
        """String representation.

        Prints the project name and its dependencies.
        """
        dependencies_str = " | ".join([str(t) for t in self._dependency_packages_metadata])
        project_str = f"Project [{self.package_name}]"
        metadata_str = str(self._package_metadata)
        other_str = f"Dependencies: [{dependencies_str}]"

        return f"{project_str}: {metadata_str};  {other_str}"


class ProjectMetadataParser:
    """Parser of python package metadata."""

    ENTRY_PATTERN = r"^([^:]*):(.*)$"

    def __init__(self, package_name: str) -> None:
        """Constructor."""
        self._project_metadata: Optional[ProjectMetadata] = None
        self._package_name = package_name

    def _get_project_metadata(self) -> ProjectMetadata:
        """Parses package metadata."""
        project_metadata = ProjectMetadata(self._package_name)
        for metadata in get_all_packages_metadata_lines(self._package_name):
            info = parse_package_metadata_lines(metadata)
            if info.name == self._package_name:
                project_metadata._package_metadata = info
            else:
                project_metadata._dependency_packages_metadata.append(info)
        return project_metadata

    @property
    def project_metadata(self) -> ProjectMetadata:
        """Gets project metadata."""
        if not self._project_metadata:
            self._project_metadata = self._get_project_metadata()
        return self._project_metadata


class CurrentProjectMetadataParser(ProjectMetadataParser):
    """Parser for current project metadata."""

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
        match = re.search(ProjectMetadataParser.ENTRY_PATTERN, line)
        if match:
            metadata_dict[match.group(1).strip()] = match.group(2).strip()
    return PackageMetadata(metadata_dict)


def generate_package_info() -> None:
    """Generates package information (egg)."""
    command = [sys.executable, "setup.py", "develop", "-v"]
    subprocess.check_call(command, cwd=configuration.get_value(ConfigurationVariable.PROJECT_ROOT))
