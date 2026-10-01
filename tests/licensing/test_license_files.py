#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from unittest.mock import patch

from datetime import datetime

from continuous_delivery_scripts.license_files import _to_copyright_date_string
from continuous_delivery_scripts.license_files import add_licence_header
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable


class TestLicenceHeader(unittest.TestCase):
    def test_proprietary_header_uses_spdx_licence_reference(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: (
                "proprietary" if key == ConfigurationVariable.FILE_LICENCE_IDENTIFIER else get_value(key)
            ),
        ):
            source = directory / "example.java"
            source.write_text("class Example {}\n", encoding="utf8")
            add_licence_header(0, directory)
            header = source.read_text(encoding="utf8")

        self.assertIn("SPDX-License-Identifier: LicenseRef-Proprietary", header)
        self.assertNotIn("SPDX-License-Identifier: proprietary", header)

    def test_copyright_dates(self):
        self.assertEqual("2020", _to_copyright_date_string(2020, 2020))
        self.assertEqual("2020-2021", _to_copyright_date_string(2020, 2021))
        this_year = datetime.now().year
        self.assertEqual(str(this_year), _to_copyright_date_string(this_year, this_year))

    def test_add_licence_header(self):
        with TemporaryDirectory() as testDir:
            test_filepath = testDir.joinpath("test.java")
            test_filepath.touch()
            file_content = []
            with open(test_filepath, "r", encoding="utf-8") as test_file:
                file_content = test_file.readlines()
            self.assertTrue(len(file_content) == 0)
            add_licence_header(3, test_filepath.parent)
            with open(test_filepath, "r", encoding="utf-8") as test_file:
                file_content = test_file.readlines()
                print(file_content)
            self.assertFalse(len(file_content) == 0)
