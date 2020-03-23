#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from mbed_tools_ci_scripts.utils.python_helpers import flatten_dictionary
import unittest


class TestPythonHelpers(unittest.TestCase):
    def test_flatten_dictionaries(self):
        dict1 = dict(a=1, b="c", d=True)
        self.assertListEqual(["a", 1, "b", "c", "d", True], flatten_dictionary(dict1))
