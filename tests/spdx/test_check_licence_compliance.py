#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Command-line licence checks, with and without report output."""

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

        self.assertEqual(self._run_command(), 0)
        self.assertEqual(list(self.root.iterdir()), [self.root / "source"])

    def test_output_directory_writes_summaries_but_no_spdx_documents(self):
        self.assertEqual(self._run_command("--output-dir", str(self.root)), 0)

        for extension in ("html", "csv", "txt", "json"):
            self.assertTrue((self.root / f"third_party_IP_report.{extension}").is_file())
        self.assertEqual(list(self.root.glob("*.spdx")), [])

    def test_noncompliant_dependency_fails_but_still_writes_requested_report(self):
        self.metadata.add_dependency_metadata(PackageMetadata({"Name": "restricted", "License": "GPL-3.0-only"}))

        self.assertEqual(self._run_command("-o", str(self.root)), 1)
        self.assertIn("restricted", (self.root / "third_party_IP_report.txt").read_text(encoding="utf8"))
        self.assertEqual(list(self.root.glob("*.spdx")), [])

    def test_unsupported_plugin_does_not_silently_pass(self):
        self.plugin.can_get_project_metadata.return_value = False

        self.assertEqual(self._run_command(), 1)
        self.plugin.get_current_spdx_project.assert_not_called()
