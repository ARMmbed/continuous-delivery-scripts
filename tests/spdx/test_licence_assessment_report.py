#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""End-to-end advisory assessments in the existing TPIP report formats."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, FileConfig, configuration
from continuous_delivery_scripts.utils.package_helpers import PackageMetadata, ProjectMetadata


class TestLicenceAssessmentReport(TestCase):
    def test_documented_manual_review_updates_assessment_but_not_allowlist_compliance(self):
        metadata = ProjectMetadata("project")
        metadata.project_metadata = PackageMetadata({"Name": "project", "License": "Proprietary"})
        metadata.add_dependency_metadata(
            PackageMetadata({"Name": "bar", "Version": "2.0", "License-Expression": "LGPL-2.1-only"})
        )
        parser = Mock()
        parser.project_metadata = metadata
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            project_config = root / "pyproject.toml"
            review_config = (
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["REVIEW"]\n'
                "[ProjectConfig.REVIEWED_LICENCE_ASSESSMENTS.bar]\n"
                'licence = "LGPL-2.1-only"\nversion = "2.0"\n'
                'reason = "Reviewed dynamic linking and redistribution (ticket LEGAL-42)."\n'
            )
            project_config.write_text(review_config, encoding="utf8")
            get_value = configuration.get_value
            overrides = {
                ConfigurationVariable.PROJECT_ROOT: root,
                ConfigurationVariable.SOURCE_DIR: "source",
                ConfigurationVariable.PROJECT_CONFIG: project_config,
                ConfigurationVariable.PROJECT_UUID: "project-id",
            }
            with patch.object(
                configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))
            ), patch.object(
                configuration, "get_value_or_default", side_effect=FileConfig(str(project_config)).get_value_or_default
            ):
                project = SpdxProject(parser)
                project.generate_licensing_summary(root)
                self.assertEqual(project.licence_assessments["bar"].status.value, "MANUALLY_REVIEWED")
                with self.assertRaisesRegex(ValueError, "non-compliant licence"):
                    project.check_licence_compliance()

            # Existing allowlist review is a separate decision. Recording it makes the CLI pass.
            project_config.write_text(
                review_config + "[ProjectConfig.PACKAGES_WITH_CHECKED_LICENCE]\n"
                'bar = "Accepted LGPL obligations after legal review LEGAL-42."\n',
                encoding="utf8",
            )
            reviewed_config = FileConfig(str(project_config))
            overrides[ConfigurationVariable.PACKAGES_WITH_CHECKED_LICENCE] = reviewed_config.get_value(
                ConfigurationVariable.PACKAGES_WITH_CHECKED_LICENCE
            )
            with patch.object(
                configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))
            ), patch.object(configuration, "get_value_or_default", side_effect=reviewed_config.get_value_or_default):
                project = SpdxProject(parser)
                project.check_licence_compliance()
                project.generate_licensing_summary(root)

            report = json.loads((root / "third_party_IP_report.json").read_text(encoding="utf8"))
            html = (root / "third_party_IP_report.html").read_text(encoding="utf8")
            text = (root / "third_party_IP_report.txt").read_text(encoding="utf8")
            with (root / "third_party_IP_report.csv").open(encoding="utf8", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file, skipinitialspace=True))

        assessment = report["packages"]["bar"]["licence_assessment"]
        self.assertEqual(report["licence_assessment_counts"]["MANUALLY_REVIEWED"], 1)
        self.assertEqual(assessment["status"], "MANUALLY_REVIEWED")
        self.assertEqual(assessment["automatic_status"], "REVIEW")
        self.assertEqual(assessment["rule"], "weak-copyleft-dependency")
        self.assertIn("LEGAL-42", assessment["manual_review"]["reason"])
        self.assertTrue(report["packages"]["bar"]["is_compliant"])
        self.assertIn("MANUALLY_REVIEWED", html)
        self.assertIn("Manual assessment review:", html)
        self.assertIn("Manual assessment review: Reviewed dynamic linking", text)
        self.assertEqual({row["Name"]: row["Assessment"] for row in rows}["bar"], "MANUALLY_REVIEWED")
        self.assertIn("LEGAL-42", {row["Name"]: row["Manual assessment review"] for row in rows}["bar"])

    def test_report_preserves_compliance_and_explains_each_dependency(self):
        metadata = ProjectMetadata("project")
        metadata.project_metadata = PackageMetadata({"Name": "project", "License": "BSD-3-Clause"})
        for name, licence in (
            ("safe", "MIT"),
            ("review", "LGPL-2.1-only"),
            ("choice", "MIT OR GPL-3.0-only"),
            ("unknown", "Unknown"),
        ):
            metadata.add_dependency_metadata(PackageMetadata({"Name": name, "License": licence}))
        parser = Mock()
        parser.project_metadata = metadata
        get_value = configuration.get_value
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            overrides = {
                ConfigurationVariable.PROJECT_ROOT: root,
                ConfigurationVariable.SOURCE_DIR: "source",
                ConfigurationVariable.PROJECT_CONFIG: root / "pyproject.toml",
                ConfigurationVariable.PROJECT_UUID: "project-id",
            }
            with patch.object(configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))):
                project = SpdxProject(parser)
                project.generate_licensing_summary(root)
                with self.assertRaisesRegex(ValueError, "non-compliant licence"):
                    project.check_licence_compliance()

            report = json.loads((root / "third_party_IP_report.json").read_text(encoding="utf8"))
            html = (root / "third_party_IP_report.html").read_text(encoding="utf8")
            text = (root / "third_party_IP_report.txt").read_text(encoding="utf8")
            with (root / "third_party_IP_report.csv").open(encoding="utf8", newline="") as csv_file:
                csv_rows = list(csv.DictReader(csv_file, skipinitialspace=True))

        self.assertEqual(
            report["licence_assessment_counts"],
            {"ALLOW": 2, "REVIEW": 1, "MANUALLY_REVIEWED": 0, "DENY": 0, "UNKNOWN": 1},
        )
        self.assertFalse(report["project"]["compliance"])
        self.assertEqual(report["packages"]["safe"]["licence_assessment"]["status"], "ALLOW")
        self.assertEqual(report["packages"]["choice"]["licence_assessment"]["selected_licence"], "MIT")
        self.assertEqual(report["packages"]["review"]["licence_assessment"]["rule"], "weak-copyleft-dependency")
        self.assertEqual(report["packages"]["unknown"]["licence_assessment"]["status"], "UNKNOWN")
        self.assertIn('<section id="licence-assessment"', html)
        self.assertIn("Dependencies needing attention", html)
        self.assertIn("Weak copyleft obligations", html)
        self.assertIn("Licence assessment: REVIEW (automatic: REVIEW)", text)
        self.assertEqual({row["Name"]: row["Assessment"] for row in csv_rows}["review"], "REVIEW")
        self.assertIn(
            "Weak copyleft obligations", {row["Name"]: row["Assessment reason"] for row in csv_rows}["review"]
        )
        self.assertNotIn("licence_assessment", report["packages"]["project"])

    def test_assessment_fail_on_is_opt_in_and_does_not_replace_the_allowlist(self):
        metadata = ProjectMetadata("project")
        metadata.project_metadata = PackageMetadata({"Name": "project", "License": "MIT"})
        metadata.add_dependency_metadata(PackageMetadata({"Name": "dependency", "License": "MIT"}))
        parser = Mock()
        parser.project_metadata = metadata
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            project_config = root / "pyproject.toml"
            project_config.write_text(
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["DENY"]\n'
                "[[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]]\n"
                'id = "permissive-dependency"\nproject_category = "*"\n'
                'dependency_category = "PERMISSIVE"\nstatus = "DENY"\nreason = "Local policy prohibition."\n',
                encoding="utf8",
            )
            get_value = configuration.get_value
            overrides = {
                ConfigurationVariable.PROJECT_ROOT: root,
                ConfigurationVariable.SOURCE_DIR: "source",
                ConfigurationVariable.PROJECT_CONFIG: project_config,
                ConfigurationVariable.PROJECT_UUID: "project-id",
            }
            file_config = FileConfig(str(project_config))
            with patch.object(
                configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))
            ), patch.object(configuration, "get_value_or_default", side_effect=file_config.get_value_or_default):
                project = SpdxProject(parser)
                self.assertEqual(project.licence_assessments["dependency"].status.value, "DENY")
                with self.assertRaisesRegex(ValueError, "Licence assessment policy failed for: dependency: DENY"):
                    project.check_licence_compliance()
