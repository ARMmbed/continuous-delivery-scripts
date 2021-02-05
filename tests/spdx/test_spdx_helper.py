#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from continuous_delivery_scripts.spdx_report.spdx_helpers import determine_checked_packages_from_configuration_entry


class TestSpdxHelpers(TestCase):
    def test_parse_configuration_entry(self):
        expected_dictionary = dict(package1="Checked", package2="Accepted licence : MIT", package3="!!!!!")
        self.assertDictEqual(
            expected_dictionary, determine_checked_packages_from_configuration_entry(expected_dictionary)
        )
        self.assertDictEqual(
            expected_dictionary,
            determine_checked_packages_from_configuration_entry(
                "package1 = Checked, package2= Accepted licence : MIT , package3=!!!!! "
            ),
        )
        self.assertDictEqual(
            expected_dictionary,
            determine_checked_packages_from_configuration_entry(
                ["package1 = Checked", " package2= Accepted licence : MIT ", " package3=!!!!! "]
            ),
        )
        expected_dictionary = dict(package1="Checked", package2="Accepted licence (MIT)", package3="!!!!!")
        self.assertDictEqual(
            expected_dictionary, determine_checked_packages_from_configuration_entry(expected_dictionary)
        )
        self.assertDictEqual(
            expected_dictionary,
            determine_checked_packages_from_configuration_entry(
                "package1 : Checked, package2= Accepted licence (MIT) , package3:!!!!! "
            ),
        )
        self.assertDictEqual(
            expected_dictionary,
            determine_checked_packages_from_configuration_entry(
                ["package1 : Checked", " package2: Accepted licence (MIT) ", " package3=!!!!! "]
            ),
        )
