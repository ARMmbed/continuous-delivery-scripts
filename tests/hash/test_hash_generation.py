#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from pathlib import Path
from continuous_delivery_scripts.utils.hash_helpers import determine_sha1_hash_of_file


class TestHashGeneration(unittest.TestCase):
    def test_file_hash_generation(self):
        # Test the generation of file hash using a known file from https://www.thinkbroadband.com/download
        # SHA1 Hash was determined using HashCheck
        self.assertEqual(
            "F3B8EEBE058415B752BEC735652A30104FE666BA",
            determine_sha1_hash_of_file(Path(__file__).parent.joinpath("fixtures", "10MB.zip")).upper(),
        )
