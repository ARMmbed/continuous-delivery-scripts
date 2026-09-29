#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from continuous_delivery_scripts.plugins.python import Python
from continuous_delivery_scripts.report_third_party_ip import generate_spdx_reports
from continuous_delivery_scripts.tag_and_release import _update_licensing_summary
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration


class TestPythonReport(TestCase):
    @mock.patch("continuous_delivery_scripts.report_third_party_ip.get_language_specifics", return_value=Python())
    def test_generates_html_licence_summary_from_installed_metadata(self, _get_language_specifics):
        with TemporaryDirectory() as output_dir:
            project = generate_spdx_reports(Path(output_dir))

            self.assertIsNotNone(project)
            html_report = Path(output_dir, "third_party_IP_report.html")
            self.assertTrue(html_report.is_file())
            self.assertIn("continuous-delivery-scripts", html_report.read_text(encoding="utf8"))
            report = json.loads(Path(output_dir, "third_party_IP_report.json").read_text(encoding="utf8"))
            self.assertIn("continuous-delivery-scripts", report["packages"])
            self.assertIn("licence_source", report["packages"]["continuous-delivery-scripts"])
            self.assertIn("licence_evidence", report["packages"]["continuous-delivery-scripts"])
            self.assertIn("manual_check", report["packages"]["continuous-delivery-scripts"])
            self.assertIn("missing_dependencies", report)

    @mock.patch("continuous_delivery_scripts.tag_and_release.get_language_specifics", return_value=Python())
    def test_release_regenerates_html_licence_summary(self, _get_language_specifics):
        get_value = configuration.get_value
        with TemporaryDirectory() as docs_dir:
            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: docs_dir
                if key == ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH
                else get_value(key),
            ):
                project = _update_licensing_summary()

            self.assertIsNotNone(project)
            self.assertTrue(Path(docs_dir, "third_party_IP_report.html").is_file())
