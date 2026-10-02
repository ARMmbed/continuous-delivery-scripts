#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Shared package metadata used by language plugins and licence reports."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Union

from continuous_delivery_scripts.utils.configuration import (
    ConfigurationVariable,
    configuration,
)
from continuous_delivery_scripts.utils.definitions import UNKNOWN

logger = logging.getLogger(__name__)


class LicenceSource(Enum):
    """Where a package's declared licence was obtained."""

    EXPRESSION = "License-Expression"
    LEGACY = "License"
    CLASSIFIER = "License-Classifier"
    CONFIGURATION = "configuration"
    TOOL = "tool"
    UNKNOWN = "unknown"


@dataclass
class _PackageFields:
    """Named, language-neutral values used by licence and SPDX reports."""

    name: str = UNKNOWN
    version: str = UNKNOWN
    author: str = UNKNOWN
    author_email: str = UNKNOWN
    licence: str = UNKNOWN
    licence_source: LicenceSource = LicenceSource.UNKNOWN
    declared_licence: str = ""
    description: str = UNKNOWN
    url: str = UNKNOWN
    licence_classifiers: List[str] = field(default_factory=list)
    licence_candidates: List[str] = field(default_factory=list)
    licence_evidence: List[Dict[str, str]] = field(default_factory=list)


class PackageMetadata:
    """Language-neutral package metadata supplied by a project plugin.

    Metadata keys follow Python Core Metadata where possible so that other
    languages can use the same SPDX and licence-reporting pipeline.
    It is based on https://www.python.org/dev/peps/pep-0314/
    https://packaging.python.org/specifications/core-metadata/
    """

    def __init__(
        self, data: Union[Mapping[str, Any], _PackageFields], licence_evidence: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """Accept named fields or adapt Python Core Metadata at the input boundary."""
        if isinstance(data, _PackageFields):
            self._fields = data
            return

        expression = str(data.get("License-Expression") or "").strip()
        legacy = str(data.get("License") or "").strip()
        classifier = str(data.get("License-Classifier") or "").strip()
        if expression:
            licence, source = expression, LicenceSource.EXPRESSION
        elif legacy and not legacy.lower().startswith("copyright") and legacy.lower() not in ("unknown", "none"):
            licence, source = legacy, LicenceSource.LEGACY
        elif classifier:
            licence, source = classifier, LicenceSource.CLASSIFIER
        else:
            licence, source = UNKNOWN, LicenceSource.UNKNOWN

        project_url = str(data.get("Project-URL") or "")
        url = str(data.get("Home-page") or project_url.partition(",")[2].strip() or UNKNOWN)
        self._fields = _PackageFields(
            name=str(data.get("Name", UNKNOWN)),
            version=str(data.get("Version", UNKNOWN)),
            author=str(data.get("Author", UNKNOWN)),
            author_email=str(data.get("Author-email", UNKNOWN)),
            licence=licence,
            licence_source=source,
            declared_licence=str(expression or legacy or "; ".join(data.get("License-Classifiers", []))),
            description=str(data.get("Summary", UNKNOWN)),
            url=url,
            licence_classifiers=list(data.get("License-Classifiers", [])),
            licence_candidates=list(data.get("Licence-Candidates", [])),
            licence_evidence=licence_evidence or [],
        )

    @classmethod
    def from_fields(
        cls,
        *,
        name: str,
        licence: str,
        licence_source: LicenceSource,
        version: str = UNKNOWN,
        url: str = UNKNOWN,
        declared_licence: Optional[str] = None,
        licence_classifiers: Optional[List[str]] = None,
        licence_candidates: Optional[List[str]] = None,
        licence_evidence: Optional[List[Dict[str, str]]] = None,
        author: str = UNKNOWN,
        author_email: str = UNKNOWN,
        description: str = UNKNOWN,
    ) -> "PackageMetadata":
        """Build metadata from named fields without relying on Python header keys."""
        return cls(
            _PackageFields(
                name=name,
                version=version,
                author=author,
                author_email=author_email,
                licence=licence,
                licence_source=licence_source,
                declared_licence=licence if declared_licence is None else declared_licence,
                description=description,
                url=url,
                licence_classifiers=list(licence_classifiers or []),
                licence_candidates=list(licence_candidates or []),
                licence_evidence=list(licence_evidence or []),
            )
        )

    @property
    def name(self) -> str:
        """Gets package's name."""
        return self._fields.name

    @property
    def version(self) -> str:
        """Gets package's version."""
        return self._fields.version

    @property
    def author(self) -> str:
        """Gets package's author."""
        return self._fields.author

    @property
    def author_email(self) -> str:
        """Gets package's author email."""
        return self._fields.author_email

    @property
    def licence(self) -> str:
        """Gets package's licence."""
        return self._fields.licence

    @property
    def licence_source(self) -> str:
        """Gets the metadata field used to determine the licence."""
        return self._fields.licence_source.value

    @property
    def has_unknown_licence(self) -> bool:
        """Whether no usable licence declaration was found."""
        return self._fields.licence_source is LicenceSource.UNKNOWN

    @property
    def declared_licence(self) -> str:
        """Gets the licence declaration as provided by the package."""
        return self._fields.declared_licence

    @property
    def licence_classifiers(self) -> List[str]:
        """Gets all licence classifiers as declared by the package."""
        return list(self._fields.licence_classifiers)

    @property
    def licence_candidates(self) -> List[str]:
        """Gets normalised SPDX licence candidates that require review."""
        return list(self._fields.licence_candidates)

    @property
    def licence_evidence(self) -> List[Dict[str, str]]:
        """Gets the packaged licence and notice file evidence."""
        return self._fields.licence_evidence

    @property
    def description(self) -> str:
        """Gets the package description."""
        return self._fields.description

    @property
    def url(self) -> str:
        """Gets package's URL."""
        return self._fields.url

    def __str__(self) -> str:
        """String representation."""
        relevant_data = [
            f"{getter}: {getattr(self, getter, None)}"
            for getter in dir(self)
            if not getter.startswith("_") and not callable(getattr(self, getter, None))
        ]
        return ", ".join(relevant_data)


class ProjectMetadata:
    """Metadata for a project."""

    def __init__(self, package_name: str) -> None:
        """Constructor."""
        self._package_metadata: PackageMetadata = PackageMetadata(dict())
        self._dependency_packages_metadata: List[PackageMetadata] = list()
        self._package_name: str = package_name
        self.missing_dependencies: List[str] = []

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
