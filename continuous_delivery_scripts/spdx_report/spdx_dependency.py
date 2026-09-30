#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of dependency SPDX Document."""

import re
from typing import TYPE_CHECKING

from continuous_delivery_scripts.utils.hash_helpers import generate_uuid_based_on_str

if TYPE_CHECKING:
    from spdx_tools.spdx.model.external_document_ref import ExternalDocumentRef


class DependencySpdxDocumentRef:
    """SPDX external document describing dependency.

    Keep each third-party dependency in a separate SPDX file and link its
    package to the project through an external document reference.
    See https://spdx.org/spdx-specification-21-web-version#h.h430e9ypa0j9
    """

    def __init__(self, name: str, namespace: str, checksum: str, package_id: str) -> None:
        """Constructor."""
        self._document_name = name
        self._document_namespace = namespace
        self._document_checksum = checksum
        self._package_id = package_id

    @property
    def document_ref_id(self) -> str:
        """Return a stable SPDX-safe external document identifier."""
        safe_name = (
            self._document_name
            if re.fullmatch(r"[A-Za-z0-9.-]+", self._document_name)
            else str(generate_uuid_based_on_str(self._document_name))
        )
        return f"DocumentRef-{safe_name}"

    @property
    def package_spdx_id(self) -> str:
        """Return the referenced package identifier in the external document."""
        return f"{self.document_ref_id}:SPDXRef-{self._package_id}"

    def generate_external_reference(self) -> "ExternalDocumentRef":
        """Generates the external SPDX reference.

        e.g.
            ExternalDocumentRef:DocumentRef-spdx-tool-1.2
            http://spdx.org/spdxdocs/spdx-tools- v1.2-3F2504E0-4F89-41D3-9A0C-0305E82C3301
            SHA1: d6a770ba38583e d4bb4525bd96e50461655d2759
        Returns:
            corresponding reference
        """
        from spdx_tools.spdx.model.checksum import Checksum, ChecksumAlgorithm
        from spdx_tools.spdx.model.external_document_ref import ExternalDocumentRef

        return ExternalDocumentRef(
            document_ref_id=self.document_ref_id,
            document_uri=self._document_namespace,
            checksum=Checksum(ChecksumAlgorithm.SHA1, self._document_checksum),
        )
