#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Definition of an SPDX Package."""

from dataclasses import dataclass
from pathlib import Path
from spdx.checksum import Algorithm
from spdx.creationinfo import Person
from spdx.document import License
from spdx.package import Package
from spdx.utils import NoAssert
from typing import List, Optional

from continuous_delivery_scripts.spdx_report.spdx_file import SpdxFile
from continuous_delivery_scripts.spdx_report.spdx_helpers import determine_spdx_value, list_project_files_for_licensing
from continuous_delivery_scripts.utils.definitions import UNKNOWN
from continuous_delivery_scripts.utils.python.package_helpers import PackageMetadata
from continuous_delivery_scripts.utils.third_party_licences import (
    UNKNOWN_LICENCE,
    cleanse_licence_expression,
    is_licence_accepted,
    determine_licence_compound,
)


@dataclass(frozen=True, order=True)
class PackageInfo:
    """Definition of a Python package.

    Attributes:
        metadata: metadata about a package from files generated from setup.py.
        root_dir: project root directory.
        source_dir: directory where package's sources are.
        uuid: unique identifier of the package.
    """

    metadata: PackageMetadata
    root_dir: Path
    source_dir: Path
    uuid: str


def _set_package_copyright(file: SpdxFile, package: Package) -> None:
    """Sets the copyright field of a package based on file copyright."""
    if file.copyright:
        package.cr_text = determine_spdx_value(file.copyright)


class SpdxPackage:
    """SPDX package.

    See https://spdx.org/spdx-specification-21-web-version#h.4i7ojhp
    """

    def __init__(self, package_info: PackageInfo, is_dependency: bool = False) -> None:
        """Constructor."""
        self._is_dependency = is_dependency
        self._package_info = package_info
        self._file_list: Optional[List[Path]] = None
        self._actual_licence: Optional[str] = None
        self._main_licence: Optional[str] = None

    @property
    def files(self) -> Optional[List[Path]]:
        """Gets package's files.

        Returns:
            list of file path or None if a dependency.
        """
        if self._is_dependency:
            return None
        if not self._file_list:
            self._file_list = [p for p in list_project_files_for_licensing(self._package_info.source_dir)]
        return self._file_list

    @property
    def id(self) -> str:
        """Gets Package's identifier.

        Returns:
            An ID
        """
        return self.name if self._is_dependency else self._package_info.uuid

    @property
    def is_dependency(self) -> bool:
        """States whether the package is a dependency or not."""
        return self._is_dependency

    @property
    def name(self) -> str:
        """Gets Package's name.

        See https://spdx.org/spdx-specification-21-web-version#h.2xcytpi

        Returns:
            corresponding string
        """
        return self._package_info.metadata.name

    @property
    def version(self) -> str:
        """Gets package's version.

        Returns:
            package version
        """
        return self._package_info.metadata.version

    @property
    def main_licence(self) -> str:
        """Gets the package's official licence.

        Returns:
            project's licence
        """
        if not self._main_licence:
            package_licence = self._package_info.metadata.licence
            self._main_licence = (
                cleanse_licence_expression(package_licence) if package_licence else UNKNOWN_LICENCE.identifier
            )
        return self._main_licence

    @property
    def is_main_licence_accepted(self) -> bool:
        """States whether the main licence of the package is part of the accepted licence list."""
        return is_licence_accepted(self.main_licence)

    @property
    def licence(self) -> str:
        """Gets the actual package's licence based on the files it contains.

        Returns:
            project's licence
        """
        if not self._actual_licence:
            files = self.get_spdx_files()
            self._actual_licence = (
                determine_licence_compound(self.main_licence, [f.licence for f in files])
                if files
                else self.main_licence
            )
        return self._actual_licence

    @property
    def is_licence_accepted(self) -> bool:
        """States whether the actual package's licence of the package is part of the accepted licence list."""
        return is_licence_accepted(self.licence)

    @property
    def author(self) -> str:
        """Gets the document's author.

        Returns:
            document's author
        """
        return self._package_info.metadata.author

    @property
    def author_email(self) -> str:
        """Gets the document author's email.

        Returns:
            document author's email
        """
        return self._package_info.metadata.author_email

    @property
    def url(self) -> str:
        """Gets the package source URL.

        Returns:
            the package homepage
        """
        return self._package_info.metadata.url

    @property
    def description(self) -> str:
        """Gets the package description.

        Returns:
            some description
        """
        return self._package_info.metadata.description

    def get_spdx_files(self) -> Optional[List[SpdxFile]]:
        """Gets package's files SPDX description.

        Returns:
            list of file descriptions or None if a dependency.
        """
        if not self.files:
            return None
        return [SpdxFile(p, self._package_info.root_dir, self.main_licence) for p in self.files]

    def generate_spdx_package(self) -> Package:
        """Generates the SPDX package.

        Example of a SPDX package:
        PackageName: eduVPN
        DataFormat: SPDXRef-1
        PackageSupplier: Organization: The Commons Conservancy eduVPN Programme
        PackageHomePage: https://eduvpn.org
        PackageLicenseDeclared: GPL-3.0+
        PackageCopyrightText: 2017, The Commons Conservancy eduVPN Programme
        PackageSummary: <text>EduVPN is designed to allow users to connect
        securely and encrypted to the Internet from any standard device.
                        </text>
        PackageComment: <text>The package includes the following libraries; see
        Relationship information.
                        </text>
        Created: 2017-06-06T09:00:00Z
        PackageDownloadLocation: git://github.com/eduVPN/reponame
        PackageDownloadLocation: git+https://github.com/eduVPN/reponame.git
        PackageDownloadLocation: git+ssh://github.com/eduVPN/reponame.git
        Creator: Person: Jane Doe

        Returns:
            the corresponding package
        """
        package = Package(
            name=determine_spdx_value(self.name),
            spdx_id=f"SPDXRef-{self.id}",
            download_location=determine_spdx_value(None),
            version=determine_spdx_value(self.version),
            file_name=determine_spdx_value(self.name),
            supplier=None,
            originator=Person(determine_spdx_value(self.author), determine_spdx_value(self.author_email)),
        )
        package.check_sum = Algorithm("SHA1", str(NoAssert()))
        package.cr_text = NoAssert()
        package.homepage = determine_spdx_value(self.url)
        package.license_declared = License.from_identifier(str(determine_spdx_value(self.main_licence)))
        package.conc_lics = License.from_identifier(str(determine_spdx_value(self.licence)))
        package.summary = determine_spdx_value(self.description)
        package.description = NoAssert()
        files = self.get_spdx_files()
        if files:
            package.files_analyzed = True
            for file in files:
                package.add_file(file.generate_spdx_file())
                package.add_lics_from_file(License.from_identifier(str(determine_spdx_value(file.licence))))
                _set_package_copyright(file, package)
            package.verif_code = determine_spdx_value(package.calc_verif_code())
        else:
            # Has to generate a dummy file because of the following rule in SDK:
            # - Package must have at least one file
            dummy_file = SpdxFile(Path(UNKNOWN), self._package_info.root_dir, self.main_licence)
            package.verif_code = NoAssert()
            package.add_file(dummy_file.generate_spdx_file())
            package.add_lics_from_file(License.from_identifier(str(determine_spdx_value(dummy_file.licence))))
        return package
