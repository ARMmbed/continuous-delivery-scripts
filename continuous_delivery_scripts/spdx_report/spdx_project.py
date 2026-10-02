#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX report for a project."""

from pathlib import Path
import os
import re
from typing import Optional, List, cast, Tuple, Dict

from continuous_delivery_scripts.spdx_report.spdx_dependency import (
    DependencySpdxDocumentRef,
)
from continuous_delivery_scripts.spdx_report.spdx_document import SpdxDocument
from continuous_delivery_scripts.spdx_report.licence_assessment import (
    LicenceAssessor,
    LicenceAssessmentPolicy,
    LicenceAssessmentResult,
)
from continuous_delivery_scripts.utils.hash_helpers import determine_sha1_hash_of_file
from continuous_delivery_scripts.utils.package_helpers import ProjectMetadataFetcher
from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    is_package_licence_manually_checked,
    get_package_manual_check,
    get_package_manual_licence,
)
from continuous_delivery_scripts.spdx_report.spdx_summary import SummaryGenerator
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.hash_helpers import generate_uuid_based_on_str
from continuous_delivery_scripts.utils.third_party_licences import UNKNOWN_LICENCE


class SpdxProject:
    """SPDX for a project.

    SPDX information about a project so that it complies with OpenChain
        See https://certification.openchainproject.or
    """

    def __init__(self, parser: ProjectMetadataFetcher) -> None:
        """Constructor."""
        self._parser = parser
        self._main_document: Optional[SpdxDocument] = None
        self._dependency_documents: Optional[List[SpdxDocument]] = None
        self._licence_assessor: Optional[LicenceAssessor] = None
        self._licence_assessments: Optional[Dict[str, LicenceAssessmentResult]] = None
        self._lookup_scancode = False

    def enable_scancode_lookup(self) -> None:
        """Opt in to LicenseDB lookups for missing assessment information."""
        if not self._lookup_scancode:
            self._lookup_scancode = True
            self._licence_assessor = None
            self._licence_assessments = None

    def _generate_documents(self) -> None:
        if self._main_document:
            return
        self._dependency_documents = list()
        project_metadata = self._parser.project_metadata
        dependencies = project_metadata.dependencies_metadata
        for dependency in dependencies:
            self._dependency_documents.append(SpdxDocument(dependency, is_dependency=True))
        self._main_document = SpdxDocument(package_metadata=project_metadata.project_metadata)

    @property
    def main_document(self) -> SpdxDocument:
        """Gets project's main SPDX document."""
        self._generate_documents()
        return cast(SpdxDocument, self._main_document)

    @property
    def dependency_documents(self) -> List[SpdxDocument]:
        """Gets the list of project's dependencies SPDX documents."""
        self._generate_documents()
        return self._dependency_documents if self._dependency_documents else list()

    @property
    def licence_assessor(self) -> LicenceAssessor:
        """Use the same loaded policy in reports and optional CI gating."""
        if self._licence_assessor is None:
            self._licence_assessor = LicenceAssessor(LicenceAssessmentPolicy.from_config(), self._lookup_scancode)
        return self._licence_assessor

    def has_assessment_gate(self) -> bool:
        """Whether an older rules-file or inline setting opts into gating."""
        return bool(self.licence_assessor.policy.fail_on)

    @property
    def licence_assessments(self) -> Dict[str, LicenceAssessmentResult]:
        """Assess already-discovered dependency licences against the project licence."""
        if self._licence_assessments is None:
            project = self.main_document.generate_spdx_package()
            assessments = {}
            for document in self.dependency_documents:
                dependency = document.generate_spdx_package()
                assessments[dependency.name] = self.licence_assessor.assess(
                    project.main_licence,
                    dependency.licence,
                    dependency.name,
                    dependency.version,
                    project.metadata.has_unknown_licence,
                    dependency.metadata.has_unknown_licence or dependency.main_licence == UNKNOWN_LICENCE.identifier,
                    get_package_manual_licence(dependency.name),
                )
            self._licence_assessments = assessments
        return self._licence_assessments

    def scancode_follow_up_warnings(self) -> List[str]:
        """Describe local policy changes needed to reproduce lookup-assisted results."""
        if not self._lookup_scancode:
            return []
        policy = self.licence_assessor.policy
        warnings = []
        for package_name, result in self.licence_assessments.items():
            for info in result.scancode_licences:
                if info.identifier in policy.classifications:
                    action = (
                        "Add a directional assessment rule under [[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]] "
                        f"for project {result.project_licence} and dependency {result.dependency_licence}."
                    )
                else:
                    category = policy.scancode_categories.get(info.category)
                    action = (
                        f'After reviewing the source, add "{info.identifier}" = "{category.value}" under '
                        "[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications] (or the project policy file)."
                        if category
                        else "Review the LicenseDB category and add a project licence classification "
                        "and directional rule."
                    )
                    if result.rule in ("directional-rule-missing", "project-needs-review"):
                        action += " Add a directional rule if the classification alone does not resolve the assessment."
                warnings.append(
                    f"{package_name}: ScanCode LicenseDB supplied {info.identifier} ({info.category}) from {info.url}. "
                    + action
                )
        return warnings

    @staticmethod
    def generate_tag_value_file(dir: Path, spdx_doc: SpdxDocument, filename: str = "LICENSE.spdx") -> str:
        """Generates the Tag file into the directory.

        See https://github.com/david-a-wheeler/spdx-tutorial#spdx-files

        Args:
            dir: output directory
            filename: file name of the document
            spdx_doc: SPDX document to write down

        Returns:
            file checksum
        """
        if not dir.exists():
            raise ValueError(f"Undefined directory: {str(dir)}")
        if not dir.is_dir():
            raise NotADirectoryError(str(dir))

        path = dir.joinpath(filename)
        from spdx_tools.spdx.writer.tagvalue.tagvalue_writer import write_document_to_stream

        with open(str(path), mode="w", encoding="utf-8") as out:
            write_document_to_stream(spdx_doc.generate_spdx_document(), out)
        return str(determine_sha1_hash_of_file(path))

    def generate_licensing_summary(self, dir: Path) -> None:
        """Generates licensing summary into the specified directory.

        Args:
            dir: output directory
        """
        SummaryGenerator(
            self.main_document.generate_spdx_package(),
            [d.generate_spdx_package() for d in self.dependency_documents],
            self._parser.project_metadata.missing_dependencies,
            self.licence_assessments,
        ).generate_summary(dir)

    @staticmethod
    def _spdx_filename(name: str) -> str:
        """Use a stable, filesystem-safe SPDX filename for any package name."""
        safe_name = (
            name
            if re.fullmatch(r"[A-Za-z0-9_.-]+", name) and name not in (".", "..")
            else str(generate_uuid_based_on_str(name))
        )
        return f"{safe_name}.spdx"

    def generate_tag_value_files(self, dir: Path) -> None:
        """Generates SPDX tag-value files into the specified directory.

        See https://github.com/david-a-wheeler/spdx-tutorial#spdx-files
        There will be a file for the current project as well as a file
        per third-party dependencies

        Args:
            dir: output directory
        """
        if not dir.exists():
            raise ValueError(f"Undefined directory: {str(dir)}")
        if not dir.is_dir():
            raise NotADirectoryError(str(dir))

        externalRefs = list()
        for spdx_dependency in self.dependency_documents:
            file_name = self._spdx_filename(spdx_dependency.name)
            checksum = SpdxProject.generate_tag_value_file(dir, spdx_dependency, file_name)
            externalRefs.append(
                DependencySpdxDocumentRef(
                    name=spdx_dependency.document_name,
                    namespace=spdx_dependency.document_namespace,
                    checksum=checksum,
                    package_id=spdx_dependency.generate_spdx_package().id,
                )
            )
        self.main_document.external_refs = externalRefs
        SpdxProject.generate_tag_value_file(dir, self.main_document, self._spdx_filename(self.main_document.name))

    def _report_issues(self, issues: Dict[str, str]) -> None:
        if issues:
            raise ValueError(
                f",{os.linesep}".join(
                    [
                        f"Package [{package_name}] has a non-compliant licence ({package_licence}) for this project"
                        for package_name, package_licence in issues.items()
                    ]
                )
            )

    def _check_one_licence_compliance(self, spdx_document: SpdxDocument, issues: Dict[str, str]) -> None:
        main_valid, actual_valid, name, main_licence, actual_licence = _check_package_licence(spdx_document)
        if not ((main_valid and actual_valid) or is_package_licence_manually_checked(name)):
            issues[name] = actual_licence if main_valid else main_licence

    def _check_package_dependencies_licence_compliance(self, issues: Dict[str, str]) -> None:
        for dependency in self.dependency_documents:
            self._check_one_licence_compliance(dependency, issues)

    def _check_package_licence_compliance(self, issues: Dict[str, str]) -> None:
        self._check_one_licence_compliance(self.main_document, issues)

    def check_licence_compliance(self) -> None:
        """Checks whether the licences of the package as well as all its dependencies are compliant.

        By compliant, it is meant that all the licences are in the list of accepted licences set for the given project.
        """
        issues: Dict[str, str] = dict()
        self._check_package_licence_compliance(issues)
        self._check_package_dependencies_licence_compliance(issues)
        if configuration.get_value(ConfigurationVariable.FAIL_ON_INCOMPLETE_LICENCE_AUDIT):
            missing = self._parser.project_metadata.missing_dependencies
            unknown = [
                package.name
                for package in [self.main_document, *self.dependency_documents]
                if (
                    package.generate_spdx_package().metadata.has_unknown_licence
                    or package.generate_spdx_package().main_licence == UNKNOWN_LICENCE.identifier
                )
                and not is_package_licence_manually_checked(package.name)
            ]
            undocumented = [
                package.name
                for package in [self.main_document, *self.dependency_documents]
                if get_package_manual_check(package.name)[0] and not get_package_manual_check(package.name)[1]
            ]
            if missing or unknown or undocumented:
                raise ValueError(
                    f"Incomplete licence audit: missing dependencies: {sorted(set(missing))}; "
                    f"unknown licences: {unknown}; undocumented exemptions: {undocumented}"
                )
        self._report_issues(issues)
        failing = [
            f"{name}: {result.status.value} ({result.rule})"
            for name, result in self.licence_assessments.items()
            if result.status in self.licence_assessor.policy.fail_on
        ]
        if failing:
            raise ValueError(f"Licence assessment policy failed for: {', '.join(failing)}")


def _check_package_licence(
    package_document: SpdxDocument,
) -> Tuple[bool, bool, str, str, str]:
    package = package_document.generate_spdx_package()
    return (
        package.is_main_licence_accepted,
        package.is_licence_accepted,
        package.name,
        package.main_licence,
        package.licence,
    )
