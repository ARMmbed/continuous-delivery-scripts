#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX report for a Python project."""

from pathlib import Path
import os
from spdx.writers.tagvalue import write_document
from typing import Optional, List, cast, Tuple, Dict

from continuous_delivery_scripts.spdx_report.spdx_dependency import DependencySpdxDocumentRef
from continuous_delivery_scripts.spdx_report.spdx_document import SpdxDocument
from continuous_delivery_scripts.utils.hash_helpers import determine_sha1_hash_of_file
from continuous_delivery_scripts.utils.python.package_helpers import ProjectMetadataFetcher
from continuous_delivery_scripts.spdx_report.spdx_helpers import is_package_licence_manually_checked
from continuous_delivery_scripts.spdx_report.spdx_summary import SummaryGenerator


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
        with open(str(path), mode="w", encoding="utf-8") as out:
            write_document(spdx_doc.generate_spdx_document(), out)
        return determine_sha1_hash_of_file(path)

    def generate_licensing_summary(self, dir: Path) -> None:
        """Generates licensing summary into the specified directory.

        Args:
            dir: output directory
        """
        SummaryGenerator(
            self.main_document.generate_spdx_package(), [d.generate_spdx_package() for d in self.dependency_documents]
        ).generate_summary(dir)

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
            file_name = f"{spdx_dependency.name}.spdx"
            checksum = SpdxProject.generate_tag_value_file(dir, spdx_dependency, file_name)
            externalRefs.append(
                DependencySpdxDocumentRef(
                    name=spdx_dependency.document_name, namespace=spdx_dependency.document_namespace, checksum=checksum
                )
            )
        self.main_document.external_refs = externalRefs
        SpdxProject.generate_tag_value_file(dir, self.main_document, f"{self.main_document.name}.spdx")

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
        self._report_issues(issues)


def _check_package_licence(package_document: SpdxDocument) -> Tuple[bool, bool, str, str, str]:
    package = package_document.generate_spdx_package()
    return (
        package.is_main_licence_accepted,
        package.is_licence_accepted,
        package.name,
        package.main_licence,
        package.licence,
    )
