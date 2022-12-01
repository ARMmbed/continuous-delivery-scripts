#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of dependency SPDX Document."""

from spdx.checksum import Algorithm
from spdx.document import ExternalDocumentRef


class DependencySpdxDocumentRef:
    """SPDX external document describing dependency.

    The specification in use as well as the current SPDX SDK do not currently
    allow  having more than one package described in a single SPDX document.
    Therefore, it has been decided to use the ExternalDocumentRef field and
    describe each third-party dependency in a separate file.
    See https://spdx.org/spdx-specification-21-web-version#h.h430e9ypa0j9
    """

    def __init__(self, name: str, namespace: str, checksum: str) -> None:
        """Constructor."""
        self._document_name = name
        self._document_namespace = namespace
        self._document_checksum = checksum

    def generate_external_reference(self) -> ExternalDocumentRef:
        """Generates the external SPDX reference.

        e.g.
            ExternalDocumentRef:DocumentRef-spdx-tool-1.2
            http://spdx.org/spdxdocs/spdx-tools- v1.2-3F2504E0-4F89-41D3-9A0C-0305E82C3301
            SHA1: d6a770ba38583e d4bb4525bd96e50461655d2759
        Returns:
            corresponding reference
        """
        return ExternalDocumentRef(
            external_document_id=self._document_name,
            spdx_document_uri=self._document_namespace,
            check_sum=Algorithm("SHA1", self._document_checksum),
        )
