#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX File."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    parse_spdx_licence,
    determine_file_licence,
    determine_file_copyright_text,
)
from continuous_delivery_scripts.utils.definitions import UNKNOWN
from continuous_delivery_scripts.utils.hash_helpers import (
    generate_uuid_based_on_str,
    determine_sha1_hash_of_file,
)
from continuous_delivery_scripts.utils.third_party_licences import (
    cleanse_licence_expression,
)

if TYPE_CHECKING:
    from spdx_tools.spdx.model.file import File


class SpdxFile:
    """SPDX File.

    See https://spdx.org/spdx-specification-21-web-version#h.nmf14n
    """

    def __init__(self, path: Path, project_root: Path, package_licence: str) -> None:
        """Constructor."""
        self._path = path
        self._project_root = project_root
        self._package_licence = package_licence

    @property
    def path(self) -> Path:
        """Gets the file path.

        Returns:
            the file path
        """
        return self._path

    @property
    def unix_relative_path(self) -> str:
        """Gets the unix relative path.

        Returns:
            the file path
        """
        if str(self.path) == UNKNOWN:
            return str(UNKNOWN)
        unix_path = str(self.path.relative_to(self._project_root)).replace("\\", "/")
        return f"./{unix_path}"

    @property
    def name(self) -> str:
        """Gets the file name.

        Returns:
            the fine name
        """
        return self._path.name

    @property
    def id(self) -> str:
        """Gets a unique identifier.

        Returns:
            a UUID
        """
        # Generates a unique Id based on the name of the file
        return str(generate_uuid_based_on_str(self.unix_relative_path))

    @property
    def sha1_check_sum(self) -> str:
        """Gets file SHA1 hash.

        Returns:
            corresponding hash
        """
        return str(determine_sha1_hash_of_file(self._path))

    @property
    def licence(self) -> str:
        """Determines licence from file notice.

        Returns:
            file's licence
        """
        file_licence = determine_file_licence(self.path)
        return str(cleanse_licence_expression(file_licence)) if file_licence else str(self._package_licence)

    @property
    def copyright(self) -> Optional[str]:
        """Determines copyright text from file notice.

        Returns:
            file's copyright text
        """
        copyright_text = determine_file_copyright_text(self.path)
        return str(copyright_text) if copyright_text is not None else None

    def generate_spdx_file(self) -> "File":
        """Generates the SPDX file.

        SPDX File example:
        FileName: ./tests/test_mbed_targets.py
        SPDXID: SPDXRef-cb9cce30c285e6083c2d19a463cbe592
        FileChecksum: SHA1: d3db49873bd2b1cab45bf81e7d88617dea6caaff
        LicenseConcluded: NOASSERTION
        FileCopyrightText: NONE

        Returns:
            the corresponding file
        """
        from spdx_tools.spdx.model.checksum import Checksum, ChecksumAlgorithm
        from spdx_tools.spdx.model.file import File, FileType
        from spdx_tools.spdx.model.spdx_none import SpdxNone

        licence = parse_spdx_licence(self.licence)
        return File(
            name=self.unix_relative_path,
            spdx_id=f"SPDXRef-{self.id}",
            checksums=[Checksum(ChecksumAlgorithm.SHA1, self.sha1_check_sum)],
            file_types=[FileType.SOURCE],
            license_concluded=licence,
            license_info_in_file=[licence],
            copyright_text=self.copyright or SpdxNone(),
        )
