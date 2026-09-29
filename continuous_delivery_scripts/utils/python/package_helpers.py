#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving Python's package information."""

import importlib.metadata as importlib_metadata
import logging
from email.message import Message
from email.parser import Parser
from pathlib import Path
from typing import Iterable, List, Set, Any, cast, Tuple, Dict, Optional

from license_expression import ExpressionError
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.package_helpers import (
    ProjectMetadataFetcher,
    PackageMetadata,
    ProjectMetadata,
)
from continuous_delivery_scripts.utils.third_party_licences import cleanse_licence_expression, OPENSOURCE_LICENCES

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
        distributions, project_metadata.missing_dependencies = _get_distributions_and_missing(self._package_name)
        for distribution in distributions:
            info = parse_package_metadata(cast(Message, distribution.metadata), distribution)
            if canonicalize_name(info.name) == canonicalize_name(self._package_name):
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


def _get_distribution_name(distribution: importlib_metadata.Distribution) -> str:
    distribution_name = getattr(distribution, "name", None)
    if distribution_name:
        return str(distribution_name)

    metadata = distribution.metadata
    if "Name" in metadata:
        return str(metadata["Name"])

    raise importlib_metadata.PackageNotFoundError("Distribution metadata does not define a package name")


def _get_distribution(package_name: str) -> importlib_metadata.Distribution:
    try:
        return importlib_metadata.distribution(package_name)
    except importlib_metadata.PackageNotFoundError:
        normalised_package_name = package_name.replace("-", "_")
        for distribution in importlib_metadata.distributions():
            if canonicalize_name(_get_distribution_name(distribution)) == canonicalize_name(normalised_package_name):
                return distribution
        raise


def _iter_dependency_distributions(
    distribution: importlib_metadata.Distribution,
    seen_packages: Set[str],
    missing_packages: Optional[List[str]] = None,
    extras: Optional[Set[str]] = None,
) -> Iterable[importlib_metadata.Distribution]:
    for requirement_text in distribution.requires or []:
        requirement = Requirement(requirement_text)
        if requirement.marker and not any(
            requirement.marker.evaluate({"extra": extra}) for extra in (extras or {""})
        ):
            continue

        normalised_name = canonicalize_name(requirement.name)
        if normalised_name in seen_packages:
            continue

        try:
            dependency_distribution = _get_distribution(requirement.name)
        except importlib_metadata.PackageNotFoundError as e:
            logger.warning(e)
            if missing_packages is not None:
                missing_packages.append(requirement.name)
            continue

        seen_packages.add(normalised_name)
        yield dependency_distribution
        yield from _iter_dependency_distributions(
            dependency_distribution, seen_packages, missing_packages, requirement.extras
        )


def _get_distributions_and_missing(package_name: str) -> Tuple[List[importlib_metadata.Distribution], List[str]]:
    """Gets the installed dependency tree and names of absent dependencies."""
    distribution = _get_distribution(package_name)
    missing: List[str] = []
    seen = {canonicalize_name(_get_distribution_name(distribution))}
    return [distribution, *_iter_dependency_distributions(distribution, seen, missing)], missing


def get_all_packages_metadata_lines(package_name: str) -> List[list]:
    """Determines the metadata lines for the present package as well as for all its dependencies."""
    distributions, _ = _get_distributions_and_missing(package_name)
    return [get_package_metadata_lines(package) for package in distributions]


def _get_licence_evidence(distribution: importlib_metadata.Distribution, metadata: Message) -> List[Dict[str, str]]:
    """Read declared licence files and notices shipped with a distribution."""
    declared = set(metadata.get_all("License-File") or [])
    evidence = []
    for entry in distribution.files or []:
        relative = Path(str(entry)).as_posix()
        parts = relative.split("/", 1)
        if len(parts) != 2 or not parts[0].endswith((".dist-info", ".egg-info")):
            continue
        filename = parts[1]
        basename = Path(filename).name.upper()
        is_notice = basename.startswith("NOTICE")
        is_declared = filename in declared or filename.removeprefix("licenses/") in declared
        is_fallback = not declared and basename.startswith(("LICENSE", "LICENCE", "COPYING"))
        if not (is_declared or is_fallback or is_notice):
            continue
        metadata_root = Path(str(distribution.locate_file(Path(parts[0])))).resolve()
        path = Path(str(distribution.locate_file(entry))).resolve()
        if path.is_relative_to(metadata_root) and path.is_file():
            evidence.append(
                {
                    "path": relative,
                    "kind": "notice" if is_notice else "licence",
                    "text": path.read_text(encoding="utf8", errors="replace"),
                }
            )
    return evidence


def parse_package_metadata(
    metadata: Message, distribution: Optional[importlib_metadata.Distribution] = None
) -> PackageMetadata:
    """Parses structured distribution metadata and preserves repeated licence classifiers."""
    data: Dict[str, Any] = dict(metadata.items())
    classifiers = [
        entry.split("::")[-1].strip()
        for entry in metadata.get_all("Classifier") or []
        if entry.startswith("License ::") and entry.split("::")[-1].strip() != "OSI Approved"
    ]
    if classifiers:
        data["License-Classifiers"] = list(dict.fromkeys(classifiers))
        identifiers = []
        for classifier in classifiers:
            try:
                identifier = cleanse_licence_expression(classifier)
            except ExpressionError:
                break
            if not OPENSOURCE_LICENCES.get_licence(identifier):
                break
            identifiers.append(identifier)
        else:
            data["Licence-Candidates"] = list(dict.fromkeys(identifiers))
            # Multiple classifiers do not establish whether the licences are alternatives or cumulative.
            if len(data["Licence-Candidates"]) == 1:
                data["License-Classifier"] = data["Licence-Candidates"][0]
    evidence = _get_licence_evidence(distribution, metadata) if distribution else []
    return PackageMetadata(data, evidence)


def parse_package_metadata_lines(metadata: list) -> PackageMetadata:
    """Parses package metadata lines and retains relevant information."""
    return parse_package_metadata(Parser().parsestr("\n".join(str(line).rstrip("\r\n") for line in metadata)))
