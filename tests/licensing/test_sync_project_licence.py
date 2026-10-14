#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from unittest.mock import patch

from continuous_delivery_scripts.spdx_report.project_licensing import ensure_project_licence_file_conforms
from continuous_delivery_scripts.spdx_report.project_licensing import RetrievedProjectLicenceText
from continuous_delivery_scripts.spdx_report.project_licensing import sync_project_licence_file
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory


class TestSyncProjectLicence(unittest.TestCase):
    def test_writes_missing_project_licence_file(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: {
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                ConfigurationVariable.PROJECT_ROOT: str(directory),
                ConfigurationVariable.LICENCE_FILE_PATH: "License.txt",
            }.get(key, get_value(key)),
        ), patch(
            "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
            return_value=RetrievedProjectLicenceText(
                identifier="Apache-2.0",
                text="Apache License 2.0",
                source="SPDX.org",
                url="https://spdx.org/licenses/Apache-2.0.json",
            ),
        ):
            licence_file = sync_project_licence_file()

            self.assertEqual((directory / "License.txt"), licence_file)
            self.assertTrue(licence_file.exists())
            self.assertEqual("Apache License 2.0\n", licence_file.read_text(encoding="utf8"))

    def test_existing_project_licence_file_is_not_rewritten(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory:
            licence_file = directory / "docs" / "License.txt"
            licence_file.parent.mkdir()
            licence_file.write_text("Apache License 2.0\n", encoding="utf8")
            with patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: {
                    ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                    ConfigurationVariable.PROJECT_ROOT: str(directory),
                    ConfigurationVariable.LICENCE_FILE_PATH: "docs/License.txt",
                }.get(key, get_value(key)),
            ), patch(
                "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
                return_value=RetrievedProjectLicenceText(
                    identifier="Apache-2.0",
                    text="Apache License 2.0",
                    source="SPDX.org",
                    url="https://spdx.org/licenses/Apache-2.0.json",
                ),
            ) as fetch:
                resolved = sync_project_licence_file()

                self.assertEqual(licence_file, resolved)
                self.assertEqual("Apache License 2.0\n", licence_file.read_text(encoding="utf8"))

        fetch.assert_called_once_with("Apache-2.0")

    def test_existing_project_licence_file_is_resynced_when_mismatched(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory:
            licence_file = directory / "LICENSE"
            licence_file.write_text("Different licence text\n", encoding="utf8")
            with patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: {
                    ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                    ConfigurationVariable.PROJECT_ROOT: str(directory),
                    ConfigurationVariable.LICENCE_FILE_PATH: "LICENSE",
                }.get(key, get_value(key)),
            ), patch(
                "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
                return_value=RetrievedProjectLicenceText(
                    identifier="Apache-2.0",
                    text="Apache License 2.0",
                    source="SPDX.org",
                    url="https://spdx.org/licenses/Apache-2.0.json",
                ),
            ):
                resolved = sync_project_licence_file()
                contents = licence_file.read_text(encoding="utf8")

                self.assertEqual(licence_file, resolved)
                self.assertEqual("Apache License 2.0\n", contents)

    def test_verbose_mismatch_logs_licence_diff(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory:
            licence_file = directory / "LICENSE"
            licence_file.write_text("Line one\nDifferent line\n", encoding="utf8")
            with patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: {
                    ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                    ConfigurationVariable.PROJECT_ROOT: str(directory),
                    ConfigurationVariable.LICENCE_FILE_PATH: "LICENSE",
                }.get(key, get_value(key)),
            ), patch(
                "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
                return_value=RetrievedProjectLicenceText(
                    identifier="Apache-2.0",
                    text="Line one\nCanonical line\n",
                    source="SPDX.org",
                    url="https://spdx.org/licenses/Apache-2.0.json",
                ),
            ), self.assertLogs(
                "continuous_delivery_scripts.spdx_report.project_licensing", level="WARNING"
            ) as logs:
                resolved = sync_project_licence_file()
                contents = licence_file.read_text(encoding="utf8")
                self.assertEqual(licence_file, resolved)
                self.assertEqual("Line one\nCanonical line\n", contents)

        rendered = "\n".join(logs.output)
        self.assertIn("Project licence file differs from canonical text:", rendered)
        self.assertIn("---", rendered)
        self.assertIn("+++ canonical (SPDX.org)", rendered)

    def test_validation_mode_fails_when_project_licence_file_does_not_match_identifier(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory:
            licence_file = directory / "LICENSE"
            licence_file.write_text("Different licence text\n", encoding="utf8")
            with patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: {
                    ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                    ConfigurationVariable.PROJECT_ROOT: str(directory),
                    ConfigurationVariable.LICENCE_FILE_PATH: "LICENSE",
                }.get(key, get_value(key)),
            ), patch(
                "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
                return_value=RetrievedProjectLicenceText(
                    identifier="Apache-2.0",
                    text="Apache License 2.0",
                    source="SPDX.org",
                    url="https://spdx.org/licenses/Apache-2.0.json",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "does not match the contents"):
                    ensure_project_licence_file_conforms(create_if_missing=False)

    def test_validation_mode_fails_when_licence_file_is_missing(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: {
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                ConfigurationVariable.PROJECT_ROOT: str(directory),
                ConfigurationVariable.LICENCE_FILE_PATH: "License.txt",
            }.get(key, get_value(key)),
        ), patch(
            "continuous_delivery_scripts.spdx_report.project_licensing.fetch_project_licence_text",
            return_value=RetrievedProjectLicenceText(
                identifier="Apache-2.0",
                text="Apache License 2.0",
                source="SPDX.org",
                url="https://spdx.org/licenses/Apache-2.0.json",
            ),
        ):
            with self.assertRaisesRegex(ValueError, "requires a project licence file"):
                ensure_project_licence_file_conforms(create_if_missing=False)

    def test_sync_rejects_compound_licence_expression(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: {
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "MIT OR Apache-2.0",
                ConfigurationVariable.PROJECT_ROOT: str(directory),
                ConfigurationVariable.LICENCE_FILE_PATH: "License.txt",
            }.get(key, get_value(key)),
        ):
            with self.assertRaisesRegex(ValueError, "does not cover compound licence expressions"):
                sync_project_licence_file()

    def test_proprietary_licence_requires_manual_file(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: {
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "proprietary",
                ConfigurationVariable.PROJECT_ROOT: str(directory),
                ConfigurationVariable.LICENCE_FILE_PATH: "License.txt",
            }.get(key, get_value(key)),
        ):
            with self.assertRaisesRegex(ValueError, "author must provide"):
                sync_project_licence_file()
