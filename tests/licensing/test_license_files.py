#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest

from datetime import datetime

from continuous_delivery_scripts.license_files import _to_copyright_date_string
from continuous_delivery_scripts.license_files import add_licence_header
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory


class TestLicenceHeader(unittest.TestCase):
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
