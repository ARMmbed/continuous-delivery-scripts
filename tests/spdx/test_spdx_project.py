#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from unittest.mock import PropertyMock, patch

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.package_helpers import ProjectMetadata, PackageMetadata
from continuous_delivery_scripts.utils.noop.package_helpers import NoOpProjectMetadataFetcher


class TestSpdxFile(TestCase):
    def test_check_licence_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "Apache 2"})

        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            SpdxProject(parser).check_licence_compliance()

    def test_check_dependency_licence_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "Apache 2"})
        metadata.add_dependency_metadata(PackageMetadata({"License": "Apache 2"}))
        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            SpdxProject(parser).check_licence_compliance()

    def test_check_licence_non_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "GPL 3"})

        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            project = SpdxProject(parser)
            with self.assertRaisesRegex(ValueError, r".*GPL-3.0*"):
                project.check_licence_compliance()

    def test_check_complex_licence_non_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "Apache Licence, Version 2 AND (BSD OR MIT) AND GPL 3"})

        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            project = SpdxProject(parser)
            with self.assertRaisesRegex(ValueError, r".*GPL-3.0*"):
                project.check_licence_compliance()

    def test_check_dependency_licence_non_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "Apache 2"})
        metadata.add_dependency_metadata(PackageMetadata({"License": "GPL 3"}))

        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            project = SpdxProject(parser)
            with self.assertRaisesRegex(ValueError, r".*GPL-3.0*"):
                project.check_licence_compliance()

    def test_check_dependency_complex_licence_non_compliance(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"License": "Apache 2"})
        metadata.add_dependency_metadata(PackageMetadata({"License": "Apache Licence 2 AND (BSD OR MIT) AND GPL 3"}))

        with patch(
            "continuous_delivery_scripts.utils.noop.package_helpers.NoOpProjectMetadataFetcher.project_metadata",
            new_callable=PropertyMock,
        ) as mock_parser:
            mock_parser.return_value = metadata
            parser = NoOpProjectMetadataFetcher("test_package")
            project = SpdxProject(parser)
            with self.assertRaisesRegex(ValueError, r".*GPL-3.0*"):
                project.check_licence_compliance()
