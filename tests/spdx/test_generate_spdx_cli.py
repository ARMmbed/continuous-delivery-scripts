#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Lookup-assisted SPDX CLI warnings follow successful compliance checks."""

from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from continuous_delivery_scripts.report_third_party_ip import main
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable


class TestGenerateSpdxCli(TestCase):
    def test_successful_opt_in_lookup_prints_follow_up(self):
        project = Mock()
        project.scancode_follow_up_warnings.return_value = [
            'dependency: add "Zlib" = "PERMISSIVE" under [ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications].'
        ]
        plugin = Mock()
        plugin.can_get_project_metadata.return_value = True
        output = StringIO()
        with patch("sys.argv", ["cd-generate-spdx", "-o", "reports", "--lookup-scancode"]), patch(
            "continuous_delivery_scripts.report_third_party_ip.get_language_specifics", return_value=plugin
        ), patch(
            "continuous_delivery_scripts.report_third_party_ip.generate_spdx_reports", return_value=project
        ) as generate, redirect_stderr(
            output
        ):
            self.assertEqual(main(), 0)

        generate.assert_called_once_with(Path("reports"), lookup_scancode=True)
        project.check_licence_compliance.assert_called_once_with()
        self.assertIn("WARNING: dependency: add", output.getvalue())
        self.assertIn("[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications]", output.getvalue())

    def test_failed_check_does_not_present_lookup_as_a_successful_remediation(self):
        project = Mock()
        project.check_licence_compliance.side_effect = ValueError("Non-compliant licence")
        plugin = Mock()
        plugin.can_get_project_metadata.return_value = True
        output = StringIO()
        with patch("sys.argv", ["cd-generate-spdx", "-o", "reports", "--lookup-scancode"]), patch(
            "continuous_delivery_scripts.report_third_party_ip.get_language_specifics", return_value=plugin
        ), patch(
            "continuous_delivery_scripts.report_third_party_ip.generate_spdx_reports", return_value=project
        ), redirect_stderr(
            output
        ):
            self.assertEqual(main(), 1)

        project.scancode_follow_up_warnings.assert_not_called()
        self.assertNotIn("WARNING: dependency", output.getvalue())

    def test_skip_go_module_download_flag_sets_configuration_override(self):
        project = Mock()
        plugin = Mock()
        plugin.can_get_project_metadata.return_value = True

        with patch.dict(os.environ, {}, clear=False), patch(
            "sys.argv", ["cd-generate-spdx", "-o", "reports", "--skip-go-module-download"]
        ), patch(
            "continuous_delivery_scripts.report_third_party_ip.get_language_specifics", return_value=plugin
        ), patch(
            "continuous_delivery_scripts.report_third_party_ip.generate_spdx_reports", return_value=project
        ):
            self.assertNotIn(ConfigurationVariable.SKIP_GO_MODULE_DOWNLOAD_FOR_LICENSING.name, os.environ)
            self.assertEqual(main(), 0)
            self.assertEqual(os.environ[ConfigurationVariable.SKIP_GO_MODULE_DOWNLOAD_FOR_LICENSING.name], "true")
