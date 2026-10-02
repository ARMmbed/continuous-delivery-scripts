#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Command-line licence checks, with and without report output."""

from contextlib import redirect_stderr, redirect_stdout
import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from continuous_delivery_scripts.check_licence_compliance import main
from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.package_helpers import PackageMetadata, ProjectMetadata


class TestCheckLicenceCompliance(TestCase):
    def setUp(self):
        """Create an isolated project so report generation cannot scan repository files."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "source").mkdir()
        self.metadata = ProjectMetadata("example")
        self.metadata.project_metadata = PackageMetadata({"Name": "example", "License": "MIT"})
        self.parser = Mock()
        self.parser.project_metadata = self.metadata
        self.plugin = Mock()
        self.plugin.can_get_project_metadata.return_value = True

    def _run_command(self, *args):
        get_value = configuration.get_value
        overrides = {
            ConfigurationVariable.PROJECT_ROOT: self.root,
            ConfigurationVariable.PROJECT_CONFIG: self.root / "pyproject.toml",
            ConfigurationVariable.SOURCE_DIR: "source",
            ConfigurationVariable.PROJECT_UUID: "example-id",
        }
        with patch.object(
            configuration, "get_value", side_effect=lambda key: overrides.get(key, get_value(key))
        ), patch(
            "continuous_delivery_scripts.check_licence_compliance.get_language_specifics", return_value=self.plugin
        ), patch(
            "sys.argv", ["cd-check-licence-compliance", *args]
        ):
            self.plugin.get_current_spdx_project.return_value = SpdxProject(self.parser)
            return main()

    def test_checks_compliance_without_writing_reports(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "dependency", "License": "MIT"}))

        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(self._run_command(), 0)
        rendered = output.getvalue()
        self.assertIn("Dependencies screened: 1", rendered)
        self.assertIn(
            "Accepted third-party licences: Apache-2.0, BSD*, CC-BY-*, JSON, MIT, Python-2.0, PSF-2.0, MPL-2.0",
            rendered,
        )
        self.assertIn("Assessment fail-on statuses: DENY", rendered)
        self.assertIn("Fail on incomplete licence audit: disabled", rendered)
        self.assertIn(
            "Dependency licence assessment: ALLOW: 1, REVIEW: 0, MANUALLY_REVIEWED: 0, DENY: 0, UNKNOWN: 0",
            rendered,
        )
        self.assertIn("Compliance with configured licence policy: PASS", rendered)
        self.assertEqual(list(self.root.iterdir()), [self.root / "source"])

    def test_output_directory_writes_summaries_but_no_spdx_documents(self):
        self.assertEqual(self._run_command("--output-dir", str(self.root)), 0)

        for extension in ("html", "csv", "txt", "json"):
            self.assertTrue((self.root / f"third_party_IP_report.{extension}").is_file())
        self.assertEqual(list(self.root.glob("*.spdx")), [])

    def test_opt_in_scancode_lookup_enriches_reports_without_spdx_documents(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "bsd-dependency", "License": "BSD-4-Clause"}))
        index = json.dumps(
            [{"spdx_license_key": "BSD-4-Clause", "category": "Permissive", "json": "bsd-4-clause.json"}]
        ).encode("utf8")
        output = StringIO()
        warnings = StringIO()
        get_policy = configuration.get_value_or_default
        with patch.object(
            configuration,
            "get_value_or_default",
            side_effect=lambda key, default: (
                ["UNKNOWN"] if key == ConfigurationVariable.LICENCE_ASSESSMENT_FAIL_ON else get_policy(key, default)
            ),
        ):
            self.assertEqual(self._run_command(), 1)
            with patch(
                "continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen", return_value=BytesIO(index)
            ) as fetch, redirect_stdout(output), redirect_stderr(warnings):
                self.assertEqual(self._run_command("--lookup-scancode", "-o", str(self.root)), 0)

        fetch.assert_called_once()
        report = json.loads((self.root / "third_party_IP_report.json").read_text(encoding="utf8"))
        assessment = report["packages"]["bsd-dependency"]["licence_assessment"]
        self.assertEqual(assessment["status"], "ALLOW")
        self.assertEqual(assessment["scancode_licences"][0]["category"], "Permissive")
        self.assertIn("bsd-4-clause.json", output.getvalue())
        self.assertIn("WARNING: bsd-dependency: ScanCode LicenseDB supplied BSD-4-Clause", warnings.getvalue())
        self.assertIn('"BSD-4-Clause" = "PERMISSIVE"', warnings.getvalue())
        self.assertIn("[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications]", warnings.getvalue())
        self.assertIn("bsd-4-clause.json", warnings.getvalue())
        self.assertIn("bsd-4-clause.json", (self.root / "third_party_IP_report.html").read_text(encoding="utf8"))
        self.assertIn("bsd-4-clause.json", (self.root / "third_party_IP_report.txt").read_text(encoding="utf8"))
        with (self.root / "third_party_IP_report.csv").open(encoding="utf8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file, skipinitialspace=True))
        self.assertIn("bsd-4-clause.json", {row["Name"]: row["ScanCode references"] for row in rows}["bsd-dependency"])
        self.assertEqual(list(self.root.glob("*.spdx")), [])

    def test_noncompliant_dependency_fails_but_still_writes_requested_report(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "restricted", "License": "GPL-3.0-only"}))

        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(self._run_command("-o", str(self.root)), 1)
        self.assertIn("restricted", (self.root / "third_party_IP_report.txt").read_text(encoding="utf8"))
        self.assertEqual(list(self.root.glob("*.spdx")), [])
        self.assertIn("Dependencies screened: 1", output.getvalue())
        self.assertIn("Compliance with configured licence policy: FAIL", output.getvalue())

    def test_verbose_output_lists_dependencies_needing_attention(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "unreviewed", "License": "MPL-2.0"}))

        with self.assertLogs("continuous_delivery_scripts.check_licence_compliance", level="WARNING") as logs:
            self.assertEqual(self._run_command("-v"), 0)

        rendered = "\n".join(logs.output)
        self.assertIn("Dependencies needing attention:", rendered)
        self.assertIn("- unreviewed: status=REVIEW", rendered)
        self.assertIn("assessed_licence=MPL-2.0", rendered)
        self.assertIn("rule=", rendered)
        self.assertIn("reason=", rendered)

    def test_non_verbose_output_omits_dependencies_needing_attention(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "unreviewed", "License": "MPL-2.0"}))

        warnings = StringIO()
        with redirect_stderr(warnings):
            self.assertEqual(self._run_command(), 0)

        self.assertNotIn("Dependencies needing attention:", warnings.getvalue())

    def test_unreviewed_weak_copyleft_does_not_fail_deny_only_gate(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "unreviewed", "License": "MPL-2.0"}))

        self.assertEqual(self._run_command(), 0)
        self.assertEqual(list(self.root.iterdir()), [self.root / "source"])

    def test_failed_lookup_assisted_check_does_not_print_success_follow_up(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "bsd-dependency", "License": "BSD-4-Clause"}))
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "restricted", "License": "GPL-3.0-only"}))
        index = json.dumps(
            [{"spdx_license_key": "BSD-4-Clause", "category": "Permissive", "json": "bsd-4-clause.json"}]
        ).encode("utf8")
        warnings = StringIO()
        with patch(
            "continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen", return_value=BytesIO(index)
        ), redirect_stderr(warnings):
            self.assertEqual(self._run_command("--lookup-scancode"), 1)
        self.assertNotIn("WARNING: bsd-dependency: ScanCode LicenseDB supplied", warnings.getvalue())

    def test_unsupported_plugin_does_not_silently_pass(self):
        self.plugin.can_get_project_metadata.return_value = False

        self.assertEqual(self._run_command(), 1)
        self.plugin.get_current_spdx_project.assert_not_called()
