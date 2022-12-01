#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from continuous_delivery_scripts.utils.versioning import calculate_version, determine_version_string
from continuous_delivery_scripts.utils.definitions import CommitType


class TestVersioning(unittest.TestCase):
    def test_calculate_version(self):
        for release_type in CommitType.choices():
            _, new_version, version_elements = calculate_version(CommitType.RELEASE, False, False)
            self.assertIsNotNone(new_version)
            self.assertNotEquals(new_version, "")
            self.assertIsNotNone(version_elements)
            self.assertGreater(len(version_elements), 0)
            _, new_version, version_elements = calculate_version(CommitType.RELEASE, True, False)
            self.assertIsNotNone(new_version)
            self.assertNotEquals(new_version, "")
            self.assertIsNotNone(version_elements)
            self.assertGreater(len(version_elements), 0)

    def test_determine_version_string(self):
        self.assertEqual("1.1.1", determine_version_string(CommitType.RELEASE, "1.1.1", {}))
        self.assertEqual("1.1.1", determine_version_string(CommitType.BETA, "1.1.1", {}))
        self.assertTrue("1.1.1" in determine_version_string(CommitType.DEVELOPMENT, "1.1.1", {}))
        self.assertGreaterEqual(len(determine_version_string(CommitType.DEVELOPMENT, "1.1.1", {})), len("1.1.1"))
