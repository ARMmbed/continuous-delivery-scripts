#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from pathlib import Path
from unittest import TestCase, mock

from pyfakefs.fake_filesystem_unittest import Patcher

from continuous_delivery_scripts.plugins.ci import CI
from continuous_delivery_scripts.plugins.golang import Go
from continuous_delivery_scripts.plugins.python import Python
from continuous_delivery_scripts.update_secrets_registry import (
    _get_secrets_baseline_file,
    _determine_exclude_files,
    _generate_detect_secrets_command_list,
    update_secrets_registry,
)


class TestUpdateSecretsRegistry(TestCase):
    @mock.patch("continuous_delivery_scripts.update_secrets_registry.get_language_specifics")
    def test_python_exclude_files(self, get_language_specifics):
        get_language_specifics.return_value = Python()

        exclude_files = _determine_exclude_files()

        self.assertIn(r".*\.html$", exclude_files)
        self.assertIn(r".*Pipfile\.lock$", exclude_files)
        self.assertIn(r".*version\.py$", exclude_files)
        self.assertIn(r"^\.circleci[\\/].*", exclude_files)
        self.assertNotIn(r".*go\.sum$", exclude_files)
        self.assertIn(r"^workflows/.*", exclude_files)

    @mock.patch("continuous_delivery_scripts.update_secrets_registry.get_language_specifics")
    def test_go_exclude_files(self, get_language_specifics):
        get_language_specifics.return_value = Go()

        exclude_files = _determine_exclude_files()

        self.assertIn(r".*go\.sum$", exclude_files)
        self.assertIn(r"^\.circleci[\\/].*", exclude_files)
        self.assertNotIn(r".*Pipfile\.lock$", exclude_files)
        self.assertIn(r"^workflows/.*", exclude_files)

    @mock.patch("continuous_delivery_scripts.update_secrets_registry.get_language_specifics")
    def test_ci_does_not_exclude_workflows(self, get_language_specifics):
        get_language_specifics.return_value = CI()

        exclude_files = _determine_exclude_files()

        self.assertNotIn(r"^workflows/.*", exclude_files)
        self.assertNotIn(r"^\.github[\\/]workflows[\\/].*", exclude_files)

    def test_generate_detect_secrets_command_list(self):
        command = _generate_detect_secrets_command_list([r".*\.html$", r".*go\.sum$"])

        self.assertEqual(
            command,
            [
                "detect-secrets",
                "scan",
                "--all-files",
                "--exclude-files",
                r".*\.html$",
                "--exclude-files",
                r".*go\.sum$",
            ],
        )

    @mock.patch("continuous_delivery_scripts.update_secrets_registry.configuration.get_value")
    def test_get_secrets_baseline_file_from_configuration(self, get_value):
        get_value.side_effect = ["/repo", ".secrets.baseline"]

        baseline_file = _get_secrets_baseline_file()

        self.assertEqual(baseline_file, Path("/repo/.secrets.baseline"))

    @mock.patch("continuous_delivery_scripts.update_secrets_registry.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.update_secrets_registry.subprocess.check_output")
    @mock.patch("continuous_delivery_scripts.update_secrets_registry.configuration.get_value")
    def test_update_secrets_registry_writes_baseline(self, get_value, check_output, get_language_specifics):
        get_language_specifics.return_value = Python()
        check_output.return_value = '{"version": "1.0"}'

        with Patcher() as patcher:
            project_root = Path("/repo")
            patcher.fs.create_dir(project_root)
            get_value.side_effect = [
                str(project_root),
                str(project_root),
                ".secrets.baseline",
                ".secrets.baseline",
            ]

            baseline_path = update_secrets_registry()

            self.assertEqual(baseline_path, project_root.joinpath(".secrets.baseline"))
            self.assertTrue(baseline_path.exists())
            self.assertEqual(baseline_path.read_text(encoding="utf8"), '{"version": "1.0"}')
            check_output.assert_called_once()
