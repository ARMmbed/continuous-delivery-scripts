#
# Copyright (C) 2020-2021 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from continuous_delivery_scripts.utils.python.python_helpers import flatten_dictionary
import unittest


class TestPythonHelpers(unittest.TestCase):
    def test_flatten_dictionaries(self):
        dict1 = dict(a=1, b="c", d=True, e=[1, 2, 3])
        self.assertListEqual(["a", 1, "b", "c", "d", True, "e", 1, 2, 3], flatten_dictionary(dict1))
