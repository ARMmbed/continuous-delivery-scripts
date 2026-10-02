#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase
from unittest.mock import patch

from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    ManualLicenceCheck,
    determine_checked_packages_from_configuration_entry,
    get_package_manual_check,
    get_package_manual_licence,
    get_package_manual_record,
)


class TestSpdxHelpers(TestCase):
    def test_structured_manual_entry_separates_licence_from_review_reason(self):
        entries = {
            "manual-package": {"licence": "Apache-2.0 OR BSD-2-Clause", "reason": "Reviewed upstream licence files."},
            "flat-package": "MIT",
        }
        with patch(
            "continuous_delivery_scripts.spdx_report.spdx_helpers.get_packages_with_checked_licence",
            return_value=entries,
        ):
            self.assertEqual(get_package_manual_check("manual.package"), (True, "Reviewed upstream licence files."))
            self.assertEqual(get_package_manual_licence("manual.package"), "Apache-2.0 OR BSD-2-Clause")
            record = get_package_manual_record("manual.package")
            self.assertIsInstance(record, ManualLicenceCheck)
            self.assertTrue(record.checked)
            self.assertEqual(record.reason, "Reviewed upstream licence files.")
            self.assertEqual(record.licence, "Apache-2.0 OR BSD-2-Clause")
            record.reason = "Updated review rationale."
            record.licence = "MIT"
            self.assertEqual((record.reason, record.licence), ("Updated review rationale.", "MIT"))
            self.assertEqual(get_package_manual_check("flat-package"), (True, "MIT"))
            self.assertEqual(get_package_manual_licence("flat-package"), "MIT")

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
