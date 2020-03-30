#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from pathlib import Path

from mbed_tools_ci_scripts.spdx_report.spdx_file import determine_file_licence


class TestSpdxFile(TestCase):
    def test_file_scanner(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "file_with_patterns.txt")
        licence = determine_file_licence(test_file)
        self.assertIsNotNone(licence)
        self.assertEqual(licence, "Apache-2.0 AND EPL-1.0+ AND (BSD OR MIT)")
