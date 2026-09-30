#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX Document."""

from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from continuous_delivery_scripts.spdx_report.spdx_dependency import (
    DependencySpdxDocumentRef,
)
from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    get_project_namespace,
)
from continuous_delivery_scripts.spdx_report.spdx_package import (
    SpdxPackage,
    PackageInfo,
)
from continuous_delivery_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from continuous_delivery_scripts.utils.hash_helpers import generate_uuid_based_on_str
from continuous_delivery_scripts.utils.package_helpers import PackageMetadata

if TYPE_CHECKING:
    from spdx_tools.spdx.model.document import Document

TOOL_NAME = "mbed-spdx-generator"
SPDX_VERSION = "SPDX-2.3"


class SpdxDocument:
    """SPDX document.

    See https://spdx.org/spdx-specification-21-web-version#h.4d34og8
    """

    def __init__(
        self,
        package_metadata: PackageMetadata,
        other_document_refs: Optional[List[DependencySpdxDocumentRef]] = None,
        is_dependency: bool = False,
        document_namespace: Optional[str] = None,
    ):
        """Constructor."""
        self._project_root = Path(configuration.get_value(ConfigurationVariable.PROJECT_ROOT))
        self._project_uuid = str(configuration.get_value(ConfigurationVariable.PROJECT_UUID))
        self._project_config = Path(configuration.get_value(ConfigurationVariable.PROJECT_CONFIG))
        self._project_source = self._project_root.joinpath(configuration.get_value(ConfigurationVariable.SOURCE_DIR))
        self._package_metadata: PackageMetadata = package_metadata
        self._is_dependency: bool = is_dependency
        self._other_document_references: List[DependencySpdxDocumentRef] = other_document_refs or []
        self._document_namespace = document_namespace
        self._spdx_package: Optional[SpdxPackage] = None

    @property
    def document_name(self) -> str:
        """Gets document name.

        See https://spdx.org/spdx-specification-21-web-version#h.wape5vaqknj2

        Returns:
            corresponding string
        """
        return f"{self.name}-{self.version}"

    @property
    def document_namespace(self) -> str:
        """Gets document namespace.

        See https://spdx.org/spdx-specification-21-web-version#h.1gdfkutofa90

        Returns:
            corresponding string
        """
        if self._document_namespace:
            return self._document_namespace
        return self._generate_namespace()

    def _generate_namespace(self) -> str:
        """Generates a document namespace."""
        if self._is_dependency:
            url_base = "http://spdx.org/spdxdocs"
            uuid = generate_uuid_based_on_str(self.document_name)
            return f"{url_base}/{self.document_name}-{uuid}"
        return str(get_project_namespace(self._project_config, self.document_name))

    @property
    def name(self) -> str:
        """Gets package's name.

        Returns:
            corresponding string
        """
        return str(self._package_metadata.name)

    @property
    def version(self) -> str:
        """Gets package version.

        Returns:
            package version
        """
        return str(self._package_metadata.version)

    @property
    def licence(self) -> str:
        """Gets the project's licence.

        Returns:
            project's licence
        """
        return str(self._package_metadata.licence)

    @property
    def author(self) -> str:
        """Gets the document's author.

        Returns:
            document's author
        """
        return str(self._package_metadata.author)

    @property
    def author_email(self) -> str:
        """Gets the document author's email.

        Returns:
            document author's email
        """
        return str(self._package_metadata.author_email)

    @property
    def organisation(self) -> str:
        """Gets the organisation.

        Returns:
            the organisation in charge
        """
        return str(configuration.get_value(ConfigurationVariable.ORGANISATION))

    @property
    def organisation_email(self) -> str:
        """Gets the organisation's email.

        Returns:
            organisation's email
        """
        return str(configuration.get_value(ConfigurationVariable.ORGANISATION_EMAIL))

    @property
    def tool_name(self) -> str:
        """Gets this generation tool's name.

        Returns:
            this tool's name
        """
        return TOOL_NAME

    @property
    def reviewer(self) -> str:
        """Gets the document's reviewer.

        Returns:
            document's reviewer
        """
        return str(configuration.get_value(ConfigurationVariable.BOT_USERNAME))

    @property
    def reviewer_email(self) -> str:
        """Gets the document reviewer's email.

        Returns:
            document reviewer's email
        """
        return str(configuration.get_value(ConfigurationVariable.BOT_EMAIL))

    @property
    def external_refs(self) -> List[DependencySpdxDocumentRef]:
        """Gets the document external references.

        Returns:
            the list of external references
        """
        return self._other_document_references

    @external_refs.setter
    def external_refs(self, external_refs: List[DependencySpdxDocumentRef]) -> None:
        """Sets the document external references."""
        self._other_document_references = external_refs

    def generate_spdx_package(self) -> SpdxPackage:
        """Generates the SPDX package for this package.

        Returns:
            corresponding SPDX package.
        """
        if not self._spdx_package:
            self._spdx_package = SpdxPackage(
                PackageInfo(
                    metadata=self._package_metadata,
                    root_dir=self._project_root,
                    source_dir=self._project_source,
                    uuid=self._project_uuid,
                ),
                is_dependency=self._is_dependency,
            )
        return self._spdx_package

    def generate_spdx_document(self) -> "Document":
        """Generates the SPDX document.

        Example of SPDX document section.
        SPDXVersion: SPDX-2.3
        DataLicense: CC0-1.0
        SPDXID: SPDXRef-DOCUMENT
        DocumentName: mbed-targets
        DocumentNamespace: http://spdx.org/spdxdocs/spdx-v2.3-3c4714e6-a7b1-4574-abb8-861149cbc590
        Creator: Person: Anonymous ()
        Creator: Organization: Anonymous ()
        Creator: Tool: reuse-0.8.0
        Created: 2020-01-20T17:53:41Z
        CreatorComment: <text>
        This document was created automatically using available reuse information consistent with REUSE.
        </text>

        Returns:
            the corresponding document
        """
        from spdx_tools.spdx.model.actor import Actor, ActorType
        from spdx_tools.spdx.model.annotation import Annotation, AnnotationType
        from spdx_tools.spdx.model.document import CreationInfo, Document
        from spdx_tools.spdx.model.relationship import Relationship, RelationshipType

        creators = [Actor(ActorType.PERSON, self.author, self.author_email or None)]
        if not self._is_dependency:
            creators.append(Actor(ActorType.ORGANIZATION, self.organisation, self.organisation_email or None))
        creators.append(Actor(ActorType.TOOL, self.tool_name))
        created = datetime.now(timezone.utc)
        creation_info = CreationInfo(
            spdx_version=SPDX_VERSION,
            spdx_id="SPDXRef-DOCUMENT",
            name=self.document_name,
            document_namespace=self.document_namespace,
            creators=creators,
            created=created,
            document_comment=(
                "This document was created automatically using available project and dependency information."
            ),
            external_document_refs=[ref.generate_external_reference() for ref in self.external_refs],
        )

        spdx_package = self.generate_spdx_package()
        package = spdx_package.generate_spdx_package()
        files = [file.generate_spdx_file() for file in spdx_package.get_spdx_files() or []]
        relationships = [Relationship("SPDXRef-DOCUMENT", RelationshipType.DESCRIBES, package.spdx_id)]
        relationships.extend(Relationship(package.spdx_id, RelationshipType.CONTAINS, file.spdx_id) for file in files)
        relationships.extend(
            Relationship(package.spdx_id, RelationshipType.DEPENDS_ON, ref.package_spdx_id)
            for ref in self.external_refs
        )
        annotations = []
        if not self._is_dependency:
            annotations.append(
                Annotation(
                    spdx_id="SPDXRef-DOCUMENT",
                    annotation_type=AnnotationType.REVIEW,
                    annotator=Actor(ActorType.PERSON, self.reviewer, self.reviewer_email or None),
                    annotation_date=created,
                    annotation_comment="Reviewed by the configured project reviewer.",
                )
            )
        return Document(
            creation_info=creation_info,
            packages=[package],
            files=files,
            relationships=relationships,
            annotations=annotations,
        )
