#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving Python's package information."""

import importlib.metadata as importlib_metadata
import logging
import re
import subprocess
import sys
from typing import Iterable, List, Any, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from continuous_delivery_scripts.utils.configuration import (
    ConfigurationVariable,
    configuration,
)
from continuous_delivery_scripts.utils.package_helpers import (
    ProjectMetadataFetcher,
    PackageMetadata,
    ProjectMetadata,
)

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
    for filename in ["METADATA", "PKG-INFO"]:
        try:
            metadata = package.read_text(filename)
            if metadata:
                return cast(list, metadata.splitlines())
        except Exception as e:
            logger.warning(e)
    return list()


def _get_distribution(package_name: str) -> importlib_metadata.Distribution:
    try:
        return importlib_metadata.distribution(package_name)
    except importlib_metadata.PackageNotFoundError:
        normalised_package_name = package_name.replace("-", "_")
        for distribution in importlib_metadata.distributions():
            distribution_name = distribution.metadata.get("Name")
            if distribution_name and canonicalize_name(distribution_name) == canonicalize_name(normalised_package_name):
                return distribution
        raise


def _iter_dependency_distributions(
    distribution: importlib_metadata.Distribution, seen_packages: set[str]
) -> Iterable[importlib_metadata.Distribution]:
    for requirement_text in distribution.requires or []:
        requirement = Requirement(requirement_text)
        if requirement.marker and not requirement.marker.evaluate():
            continue

        normalised_name = canonicalize_name(requirement.name)
        if normalised_name in seen_packages:
            continue

        try:
            dependency_distribution = _get_distribution(requirement.name)
        except importlib_metadata.PackageNotFoundError as e:
            logger.warning(e)
            continue

        seen_packages.add(normalised_name)
        yield dependency_distribution
        yield from _iter_dependency_distributions(dependency_distribution, seen_packages)


def get_all_packages_metadata_lines(package_name: str) -> List[list]:
    """Determines the metadata lines for the present package as well as for all its dependencies."""
    distribution = _get_distribution(package_name)
    distribution_name = distribution.metadata.get("Name", package_name)
    seen_packages = {canonicalize_name(distribution_name)}
    all_distributions = [
        distribution,
        *_iter_dependency_distributions(distribution, seen_packages),
    ]
    return [get_package_metadata_lines(package) for package in all_distributions]


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
