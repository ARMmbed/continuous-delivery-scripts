#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX File."""

from pathlib import Path
from spdx.checksum import Algorithm
from spdx.document import License
from spdx.file import File, FileType
from typing import Optional

from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    determine_spdx_value,
    determine_file_licence,
    determine_file_copyright_text,
)
from continuous_delivery_scripts.utils.definitions import UNKNOWN
from continuous_delivery_scripts.utils.hash_helpers import generate_uuid_based_on_str, determine_sha1_hash_of_file
from continuous_delivery_scripts.utils.third_party_licences import cleanse_licence_expression


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
            return UNKNOWN
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
        return generate_uuid_based_on_str(self.unix_relative_path)

    @property
    def sha1_check_sum(self) -> str:
        """Gets file SHA1 hash.

        Returns:
            corresponding hash
        """
        return determine_sha1_hash_of_file(self._path)

    @property
    def licence(self) -> str:
        """Determines licence from file notice.

        Returns:
            file's licence
        """
        file_licence = determine_file_licence(self.path)
        return cleanse_licence_expression(file_licence) if file_licence else self._package_licence

    @property
    def copyright(self) -> Optional[str]:
        """Determines copyright text from file notice.

        Returns:
            file's copyright text
        """
        return determine_file_copyright_text(self.path)

    def generate_spdx_file(self) -> File:
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
        source_file = File(determine_spdx_value(self.unix_relative_path))
        source_file.type = FileType.SOURCE
        source_file.comment = determine_spdx_value(None)
        source_file.chk_sum = Algorithm("SHA1", self.sha1_check_sum)
        source_file.conc_lics = License.from_identifier(str(determine_spdx_value(self.licence)))
        source_file.spdx_id = f"SPDXRef-{self.id}"
        source_file.copyright = determine_spdx_value(self.copyright)
        source_file.add_lics(License.from_identifier(str(determine_spdx_value(self.licence))))
        return source_file
