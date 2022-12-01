#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving Python's package information."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.definitions import UNKNOWN

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

    def add_dependency_metadata(self, dependency_metadata: PackageMetadata) -> None:
        """Adds metadata about a dependency."""
        self._dependency_packages_metadata.append(dependency_metadata)

    @property
    def project_metadata(self) -> PackageMetadata:
        """Gets project metadata."""
        return self._package_metadata

    @project_metadata.setter
    def project_metadata(self, package_metadata: PackageMetadata) -> None:
        """Sets project metadata."""
        self._package_metadata = package_metadata

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


class ProjectMetadataFetcher(ABC):
    """Fetches package metadata e.g. dependencies."""

    def __init__(self, package_name: str) -> None:
        """Constructor."""
        self._project_metadata: Optional[ProjectMetadata] = None
        self._package_name = package_name

    @property
    def project_metadata(self) -> ProjectMetadata:
        """Gets project metadata."""
        if not self._project_metadata:
            self._project_metadata = self.fetch_project_metadata()
        return self._project_metadata

    @abstractmethod
    def fetch_project_metadata(self) -> ProjectMetadata:
        """Fetches the project metadata."""
        pass


class CurrentProjectMetadataFetcher(ProjectMetadataFetcher):
    """Fetches the current project metadata."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__(configuration.get_value(ConfigurationVariable.PACKAGE_NAME))
