#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import json
from importlib.util import find_spec
from unittest import TestCase
from unittest import skipUnless

from unittest.mock import Mock, PropertyMock, patch
from pathlib import Path
from tempfile import TemporaryDirectory

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.package_helpers import ProjectMetadata, PackageMetadata
from continuous_delivery_scripts.utils.noop.package_helpers import NoOpProjectMetadataFetcher
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.hash_helpers import generate_uuid_based_on_str


class TestSpdxFile(TestCase):
    @skipUnless(find_spec("spdx") and find_spec("pkg_resources"), "Legacy SPDX writer is required")
    def test_proprietary_project_and_file_generate_referenced_licence(self):
        metadata = ProjectMetadata("example")
        metadata.project_metadata = PackageMetadata(
            {"Name": "example", "License": "Proprietary"},
            [
                {"kind": "licence", "path": "https://example.org/licences/proprietary", "text": ""},
                {"kind": "licence", "path": "LICENSE", "text": ""},
                {"kind": "notice", "path": "https://example.org/notice", "text": ""},
            ],
        )
        metadata.add_dependency_metadata(PackageMetadata({"Name": "vendor", "License": "MIT"}))
        parser = Mock()
        parser.project_metadata = metadata
        get_value = configuration.get_value

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "main.go").write_text("// SPDX-License-Identifier: proprietary\npackage main\n", encoding="utf8")
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[spdx]\nCreatorWebsite = "example.org"\nPathToSpdx = "spdx"\nUUID = "test"\n', encoding="utf8"
            )
            overrides = {
                ConfigurationVariable.PROJECT_ROOT: root,
                ConfigurationVariable.PROJECT_CONFIG: project_config,
                ConfigurationVariable.SOURCE_DIR: "source",
                ConfigurationVariable.PROJECT_UUID: "test",
            }
            with patch.object(configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))):
                project = SpdxProject(parser)
                project.check_licence_compliance()
                project.generate_tag_value_files(root)
                spdx = (root / "example.spdx").read_text(encoding="utf8")

                self.assertIn("PackageLicenseDeclared: LicenseRef-Proprietary", spdx)
                self.assertIn("LicenseInfoInFile: LicenseRef-Proprietary", spdx)
                self.assertIn("LicenseID: LicenseRef-Proprietary", spdx)
                self.assertEqual(spdx.count("LicenseID: LicenseRef-Proprietary"), 1)
                self.assertIn("https://spdx.github.io/spdx-spec/v2.3/other-licensing-information-detected/", spdx)
                self.assertIn("LicenseCrossReference: https://example.org/licences/proprietary", spdx)
                self.assertNotIn("LicenseCrossReference: LICENSE", spdx)
                self.assertNotIn("LicenseCrossReference: https://example.org/notice", spdx)

                metadata.add_dependency_metadata(
                    PackageMetadata({"Name": "proprietary-vendor", "License": "Proprietary"})
                )
                SpdxProject(parser).generate_tag_value_files(root)
                dependency_spdx = (root / "proprietary-vendor.spdx").read_text(encoding="utf8")
                self.assertIn("PackageLicenseDeclared: LicenseRef-Proprietary", dependency_spdx)
                self.assertIn("LicenseID: LicenseRef-Proprietary", dependency_spdx)
                with self.assertRaisesRegex(ValueError, "proprietary-vendor"):
                    SpdxProject(parser).check_licence_compliance()

    def test_summary_shows_configured_licence_policy(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        parser = Mock()
        parser.project_metadata = metadata
        get_value = configuration.get_value

        with TemporaryDirectory() as output_dir, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: (
                ["MIT", "BSD*"] if key == ConfigurationVariable.ACCEPTED_THIRD_PARTY_LICENCES else get_value(key)
            ),
        ):
            SpdxProject(parser).generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")

        self.assertIn("<h3>Configured licence policy</h3>", html)
        self.assertIn("<code>MIT</code>", html)
        self.assertIn("<code>BSD*</code>", html)
        self.assertNotIn("<code>Apache-2.0</code>", html)

    @patch("continuous_delivery_scripts.spdx_report.spdx_helpers.get_packages_with_checked_licence")
    def test_manual_review_is_separate_from_automatic_assessment(self, checked_licences):
        checked_licences.return_value = {
            "manual-package": "BSD-3-Clause",
            "reviewed-package": "BSD-3-Clause",
        }
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        metadata.add_dependency_metadata(PackageMetadata({"Name": "manual-package", "License": "Unknown"}))
        metadata.add_dependency_metadata(
            PackageMetadata({"Name": "reviewed-package", "License-Expression": "BSD-3-Clause"})
        )
        parser = Mock()
        parser.project_metadata = metadata

        with TemporaryDirectory() as output_dir:
            SpdxProject(parser).generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            report = json.loads(Path(output_dir, "third_party_IP_report.json").read_text(encoding="utf8"))

        self.assertIn("A manual review record contains a separately verified licence or an exemption reason", html)
        manual_anchor = f"package-{generate_uuid_based_on_str('manual-package')}"
        manual_row = html.split(f'id="{manual_anchor}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("<strong>Automatic assessment:</strong>", manual_row)
        self.assertIn("Does not meet the configured licence policy.", manual_row)
        self.assertIn("<strong>Manual review record:</strong> BSD-3-Clause", manual_row)
        self.assertEqual(manual_row.count("BSD-3-Clause"), 1)

        reviewed_anchor = f"package-{generate_uuid_based_on_str('reviewed-package')}"
        reviewed_row = html.split(f'id="{reviewed_anchor}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("Meets the configured licence policy.", reviewed_row)
        self.assertIn("<strong>Manual review record:</strong> BSD-3-Clause", reviewed_row)
        self.assertIn(
            "accepted after manual review: BSD-3-Clause",
            report["packages"]["manual-package"]["licence_compliance_details"],
        )

    def test_html_report_highlights_compliance_and_safe_references(self):
        metadata = ProjectMetadata("example")
        metadata.project_metadata = PackageMetadata(
            {"Name": "example", "License-Expression": "MIT", "Home-page": "https://example.com"}
        )
        metadata.add_dependency_metadata(
            PackageMetadata(
                {"Name": "restricted", "License-Expression": "GPL-3.0-only", "Home-page": "javascript:alert(1)"}
            )
        )
        parser = Mock()
        parser.project_metadata = metadata

        with TemporaryDirectory() as output_dir:
            SpdxProject(parser).generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            for extension, label in (("csv", "CSV"), ("json", "JSON"), ("txt", "text")):
                filename = f"third_party_IP_report.{extension}"
                self.assertTrue(Path(output_dir, filename).is_file())
                self.assertIn(f'href="{filename}" download="{filename}">Download {label}</a>', html)

        self.assertIn('<html lang="en">', html)
        self.assertIn('<h2 id="downloads-heading">Download this report</h2>', html)
        self.assertIn('<meta name="viewport"', html)
        self.assertIn('<a href="#package-licences">Package licences</a>', html)
        self.assertIn('<table id="third_party_ip">', html)
        self.assertIn('<th scope="col">Licence</th>', html)
        self.assertIn('<span class="status status--error">Not compliant</span>', html)
        self.assertIn('<span class="status status--error">Needs review</span>', html)
        self.assertIn("<p>The project or one or more dependencies do not meet the configured licence policy.</p>", html)
        self.assertIn('href="https://example.com"', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('<a href="#dependency-summary">Dependency summary</a>', html)
        anchor = f"package-{generate_uuid_based_on_str('restricted')}"
        self.assertIn(f'<a href="#{anchor}">restricted</a>', html)
        self.assertIn(f'<tr id="{anchor}"', html)
        self.assertIn("The project and each discovered dependency included in this report.", html)
        self.assertIn("Dependencies expected but not found in the audited environment.", html)
        self.assertIn("Packages without a usable licence declaration, including those manually reviewed.", html)
        self.assertIn("Manual licence exceptions without a recorded reason.", html)

    def test_generated_report_is_linked_from_documentation_index_once(self):
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        parser = Mock()
        parser.project_metadata = metadata

        with TemporaryDirectory() as output_dir:
            index = Path(output_dir, "index.html")
            index.write_text("<html><body><main><h1>Project overview</h1></main></body></html>", encoding="utf8")
            project = SpdxProject(parser)
            project.generate_licensing_summary(Path(output_dir))
            project.generate_licensing_summary(Path(output_dir))

            html = index.read_text(encoding="utf8")
            self.assertIn('<a href="third_party_IP_report.html">View the report</a>', html)
            self.assertEqual(html.count('href="third_party_IP_report.html"'), 1)
            self.assertLess(html.index("third-party-ip-report"), html.index("</main>"))
            report = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            self.assertIn("<p>The project is licensed under the <strong>MIT</strong> licence.</p>", report)
            self.assertIn("<p>The project and all assessed dependencies meet the configured licence policy, ", report)
            text_report = Path(output_dir, "third_party_IP_report.txt").read_text(encoding="utf8")
            self.assertIn("The project is licensed under the MIT licence.", text_report)
            self.assertIn("Audit gaps highlight missing or uncertain dependency licence information", report)
            self.assertIn("No dependencies were included in this report.", report)

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
            self.assertIn("Missing dependencies have no detailed row", html)
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
            self.assertIn("Unknown licences (including manually reviewed)", html)
            anchor = f"package-{generate_uuid_based_on_str('test_package')}"
            self.assertIn(f'<li><a href="#{anchor}">test_package</a></li>', html)
            self.assertIn(f'<tr id="{anchor}"', html)

    @patch("continuous_delivery_scripts.spdx_report.spdx_helpers.get_packages_with_checked_licence")
    def test_strict_audit_requires_a_reason_for_manual_exemptions(self, checked_licences):
        checked_licences.return_value = {"test_package": ""}
        metadata = ProjectMetadata("test_package")
        metadata.project_metadata = PackageMetadata({"Name": "test_package", "License": "MIT"})
        parser = Mock()
        parser.project_metadata = metadata
        project = SpdxProject(parser)
        get_value = configuration.get_value

        with TemporaryDirectory() as output_dir:
            project.generate_licensing_summary(Path(output_dir))
            html = Path(output_dir, "third_party_IP_report.html").read_text(encoding="utf8")
            anchor = f"package-{generate_uuid_based_on_str('test_package')}"
            self.assertIn(f'<li><a href="#{anchor}">test_package</a></li>', html)
            self.assertIn(f'<tr id="{anchor}"', html)

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
