#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX report for a Python project."""

from pathlib import Path
from spdx.writers.tagvalue import write_document

from mbed_tools_ci_scripts.spdx_report.spdx_dependency import DependencySpdxDocumentRef
from mbed_tools_ci_scripts.spdx_report.spdx_document import SpdxDocument
from mbed_tools_ci_scripts.utils.hash_helpers import determine_sha1_hash_of_file
from mbed_tools_ci_scripts.utils.package_helpers import ProjectMetadataParser


class SpdxProject:
    """SPDX for a project.

    SPDX information about a project so that it complies with OpenChain
        See https://certification.openchainproject.or
    """

    def __init__(self, parser: ProjectMetadataParser) -> None:
        """Constructor."""
        self._parser = parser

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
        with open(path, mode="w", encoding="utf-8") as out:
            write_document(spdx_doc.generate_spdx_document(), out)
        return determine_sha1_hash_of_file(path)

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

        project_metadata = self._parser.project_metadata
        externalRefs = []
        dependencies = project_metadata.dependencies_metadata
        for dependency in dependencies:
            spdx_dependency = SpdxDocument(dependency, is_dependency=True)
            file_name = f"{spdx_dependency.name}.spdx"
            checksum = SpdxProject.generate_tag_value_file(dir, spdx_dependency, file_name)
            externalRefs.append(
                DependencySpdxDocumentRef(
                    name=spdx_dependency.document_name, namespace=spdx_dependency.document_namespace, checksum=checksum,
                )
            )
        main_document = SpdxDocument(
            package_metadata=project_metadata.project_metadata, other_document_refs=externalRefs,
        )
        SpdxProject.generate_tag_value_file(dir, main_document, f"{main_document.name}.spdx")
