#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from continuous_delivery_scripts.check_project_config import main
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory
from continuous_delivery_scripts.utils.project_config_schema import validate_project_config


class TestValidateProjectConfig(TestCase):
    def test_accepts_valid_project_config(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text(
                "[ProjectConfig]\n"
                'PROJECT_ROOT = "."\n'
                'PROJECT_NAME = "Example"\n'
                'PACKAGE_NAME = "example"\n'
                'PROGRAMMING_LANGUAGE = "Python"\n'
                'FILE_LICENCE_IDENTIFIER = "Apache-2.0"\n'
                'LICENCE_FILE_PATH = "LICENSE"\n'
                'RELEASE_BRANCH_PATTERN = "^release.*$"\n',
                encoding="utf8",
            )

            self.assertEqual([], validate_project_config(str(config)))

    def test_reports_unknown_key(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text("[ProjectConfig]\nUNKNOWN_KEY = true\n", encoding="utf8")

            errors = validate_project_config(str(config))

        self.assertIn("Unknown ProjectConfig key: UNKNOWN_KEY", errors)

    def test_reports_invalid_regex(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text('[ProjectConfig]\nRELEASE_BRANCH_PATTERN = "(["\n', encoding="utf8")

            errors = validate_project_config(str(config))

        self.assertEqual(1, len(errors))
        self.assertIn("RELEASE_BRANCH_PATTERN is not a valid regular expression", errors[0])

    def test_reports_invalid_language(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text('[ProjectConfig]\nPROGRAMMING_LANGUAGE = "Pascal"\n', encoding="utf8")

            errors = validate_project_config(str(config))

        self.assertEqual(1, len(errors))
        self.assertIn("PROGRAMMING_LANGUAGE must be one of:", errors[0])

    def test_reports_invalid_inline_licence_assessment_policy(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text(
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\n" "schema_version = 2\n",
                encoding="utf8",
            )

            errors = validate_project_config(str(config))

        self.assertEqual(1, len(errors))
        self.assertIn("LICENCE_ASSESSMENT configuration is invalid", errors[0])


class TestCheckProjectConfigCli(TestCase):
    def test_returns_zero_for_valid_project_config(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text('[ProjectConfig]\nPROGRAMMING_LANGUAGE = "Python"\n', encoding="utf8")
            with patch("sys.argv", ["cd-check-project-config", "--config-file", str(config)]), patch(
                "sys.stdout", new_callable=StringIO
            ) as output:
                self.assertEqual(main(), 0)

        self.assertIn("Project configuration is valid.", output.getvalue())

    def test_returns_one_for_invalid_project_config(self):
        with TemporaryDirectory() as directory:
            config = Path(directory, "pyproject.toml")
            config.write_text("[ProjectConfig]\nUNKNOWN_KEY = true\n", encoding="utf8")
            with patch("sys.argv", ["cd-check-project-config", "--config-file", str(config)]):
                self.assertEqual(main(), 1)
