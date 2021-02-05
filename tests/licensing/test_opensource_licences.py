#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest

from continuous_delivery_scripts.utils.third_party_licences import (
    parse_licence,
    iter_licenses,
    OpenSourceLicences,
    Licence,
    get_allowed_opensource_licences,
    determine_licences_not_in_list,
    is_licence_accepted,
    determine_licence_compound,
    determine_allowed_opensource_licences_from_string,
    cleanse_licence_expression,
    cleanse_licence_descriptor,
)

APACHE2_LICENCE = Licence(
    reference_number="26",
    identifier="Apache-2.0",
    name="Apache License 2.0",
    is_deprecated=False,
    is_osi_approved=True,
    url="http://spdx.org/licenses/Apache-2.0.json",
    reference="./Apache-2.0.html",
)


class TestLicences(unittest.TestCase):
    def test_licence_parse(self):
        licence = {
            "reference": "./Apache-2.0.html",
            "isDeprecatedLicenseId": False,
            "isFsfLibre": True,
            "detailsUrl": "http://spdx.org/licenses/Apache-2.0.json",
            "referenceNumber": "26",
            "name": "Apache License 2.0",
            "licenseId": "Apache-2.0",
            "seeAlso": ["http://www.apache.org/licenses/LICENSE-2.0", "https://opensource.org/licenses/Apache-2.0"],
            "isOsiApproved": True,
        }
        self.assertEqual(APACHE2_LICENCE, parse_licence(licence))

    def test_licences_parse(self):
        licences = {
            "licenseListVersion": "3.6",
            "licenses": [
                {
                    "reference": "./0BSD.html",
                    "isDeprecatedLicenseId": False,
                    "detailsUrl": "http://spdx.org/licenses/0BSD.json",
                    "referenceNumber": "319",
                    "name": "BSD Zero Clause License",
                    "licenseId": "0BSD",
                    "seeAlso": ["http://landley.net/toybox/license.html"],
                    "isOsiApproved": True,
                },
                {
                    "reference": "./Apache-2.0.html",
                    "isDeprecatedLicenseId": False,
                    "isFsfLibre": True,
                    "detailsUrl": "http://spdx.org/licenses/Apache-2.0.json",
                    "referenceNumber": "26",
                    "name": "Apache License 2.0",
                    "licenseId": "Apache-2.0",
                    "seeAlso": [
                        "http://www.apache.org/licenses/LICENSE-2.0",
                        "https://opensource.org/licenses/Apache-2.0",
                    ],
                    "isOsiApproved": True,
                },
            ],
        }

        parsed_licences = [licence for licence in iter_licenses(licences)]
        self.assertIsNotNone(parsed_licences)
        self.assertEqual(len(parsed_licences), 2)
        self.assertIn(APACHE2_LICENCE, parsed_licences)

    def test_cleanse_licence_descriptor(self):
        self.assertEqual(cleanse_licence_descriptor("BSD License"), "BSD")
        self.assertEqual(cleanse_licence_descriptor("MIT License"), "MIT")
        self.assertEqual(cleanse_licence_descriptor("apache"), "Apache-2.0")
        self.assertEqual(cleanse_licence_expression("Apache Software License"), "Apache-2.0")
        self.assertEqual(cleanse_licence_expression("public domain Python 2-Clause BSD GPL 3"), "Python-2.0")
        self.assertEqual(cleanse_licence_expression("Python Software Foundation License"), "Python-2.0")
        self.assertEqual(cleanse_licence_expression("Dual License"), "Unknown")

    def test_get_licence(self):
        licences = OpenSourceLicences()
        for licence in [
            "Apache 2.0",
            "Apache Licence, Version 2.0",
            "The Apache License, Version 2.0",
            "OSI Approved::The Apache License, Version 2.0",
            "Apache 2",
            "Apache License Version 2.0",
            "Apache License, Version 2.0",
            "Apache License 2.0",
            "Apache-2",
            "Apache-2.0",
        ]:
            self.assertEqual(APACHE2_LICENCE, licences.get_licence(licence))

    def test_licences_evaluation(self):
        self.assertEqual(
            determine_licence_compound("Apache-2.0", ["Apache-2.0", "Apache-2.0", "BSD OR MIT"]),
            "Apache-2.0 AND (BSD OR MIT)",
        )

    def test_cleanse_licence_expression(self):
        self.assertEqual(
            cleanse_licence_expression("Apache-2.0 AND (BSD License OR MIT License) AND Apache 2"),
            "Apache-2.0 AND (0BSD OR MIT)",
        )
        self.assertEqual(
            cleanse_licence_expression(
                "OSI Approved::The Apache License Version 2.0 AND (BSD Zero Clause License OR MIT) AND Apache 2.0"
            ),
            "Apache-2.0 AND (0BSD OR MIT)",
        )

    def test_licences_not_in_list(self):
        self.assertEqual(
            [
                licence
                for licence in determine_licences_not_in_list(
                    "Apache-2.0 AND (BSD OR MIT)", ["Apache-2.0", "MIT", "BSD"]
                )
            ],
            [],
        )
        self.assertEqual(
            [
                licence
                for licence in determine_licences_not_in_list("Apache-2.0 AND (BSD OR MIT)", ["Apache-2.0", "MIT"])
            ],
            ["BSD"],
        )
        self.assertEqual(
            [licence for licence in determine_licences_not_in_list("Apache-2.0 AND (BSD OR MIT)", [])],
            ["Apache-2.0", "BSD", "MIT"],
        )

    def test_if_licence_accepted(self):
        self.assertTrue(is_licence_accepted("Apache-2.0"))
        self.assertFalse(is_licence_accepted("unknown"))
        self.assertTrue(is_licence_accepted("GPL or Apache-2.0"))
        self.assertFalse(is_licence_accepted("GPL and Apache-2.0"))

    def test_allowed_opensource_licences_from_string(self):
        self.assertIn(APACHE2_LICENCE, determine_allowed_opensource_licences_from_string("Apache 2"))
        self.assertEqual(len([licence for licence in determine_allowed_opensource_licences_from_string("Apache 2")]), 1)
        self.assertGreater(
            len([licence for licence in determine_allowed_opensource_licences_from_string("Apache*")]), 1
        )
        self.assertEqual(len([licence for licence in determine_allowed_opensource_licences_from_string("BSD")]), 1)
        self.assertGreater(len([licence for licence in determine_allowed_opensource_licences_from_string("BSD*")]), 1)

    def test_allowed_third_party_licences(self):
        self.assertIn(APACHE2_LICENCE, get_allowed_opensource_licences())
