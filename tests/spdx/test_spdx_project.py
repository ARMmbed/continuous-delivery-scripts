#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from unittest.mock import Mock, PropertyMock, patch
from pathlib import Path
from tempfile import TemporaryDirectory

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.package_helpers import ProjectMetadata, PackageMetadata
from continuous_delivery_scripts.utils.noop.package_helpers import NoOpProjectMetadataFetcher
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable


class TestSpdxFile(TestCase):
    def test_missing_dependency_is_reported_and_can_fail_the_audit(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        metadata.missing_dependencies = ["missing-dependency"]
        parser = Mock()
        parser.project_metadata = metadata
        project = SpdxProject(parser)

        with TemporaryDirectory() as output_dir:
            project.generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            self.assertIn("missing-dependency", html)
            self.assertIn("Incomplete audit", html)

        project.check_licence_compliance()  # Strict handling is opt-in.

        get_value = configuration.get_value
        with patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: (
                True if key == ConfigurationVariable.FAIL_ON_INCOMPLETE_LICENCE_AUDIT else get_value(key)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "missing-dependency"):
                project.check_licence_compliance()

    def test_unrecognised_licence_is_reported_without_breaking_report_generation(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "A (B)"})
        parser = Mock()
        parser.project_metadata = metadata
        project = SpdxProject(parser)

        with TemporaryDirectory() as output_dir:
            project.generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            self.assertIn("Unknown licences (including manually reviewed): test_package", html)

    @patch("continuous_delivery_scripts.spdx_report.spdx_helpers.get_packages_with_checked_licence")
    def test_strict_audit_requires_a_reason_for_manual_exemptions(self, checked_licences):
        checked_licences.return_value = {"test_package": ""}
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        parser = Mock()
        parser.project_metadata = metadata
        project = SpdxProject(parser)
        get_value = configuration.get_value

        with patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: (
                True if key == ConfigurationVariable.FAIL_ON_INCOMPLETE_LICENCE_AUDIT else get_value(key)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "undocumented exemptions: \\['test_package'\\]"):
                project.check_licence_compliance()

    def test_licence_evidence_is_escaped_in_html(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata(
            {"Name": "test_package", "License-Expression": "MIT"},
            [{"kind": "licence", "path": "LICENSE", "text": "<script>alert(1)</script>"}],
        )
        parser = Mock()
        parser.project_metadata = metadata

        with TemporaryDirectory() as output_dir:
            SpdxProject(parser).generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertNotIn("<script>", html)

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
