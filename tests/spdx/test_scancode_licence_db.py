#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Optional, bounded LicenseDB lookups and conservative policy fallback."""

import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from continuous_delivery_scripts.spdx_report.licence_assessment import (
    LicenceAssessment,
    LicenceAssessmentPolicy,
    LicenceAssessor,
)
from continuous_delivery_scripts.spdx_report.scancode_licence_db import ScanCodeLicenceDB

SCANCODE_INDEX = json.dumps(
    [
        {"spdx_license_key": "Zlib", "category": "Permissive", "json": "zlib.json"},
        {"spdx_license_key": "EPL-2.0", "category": "Copyleft Limited", "json": "epl-2.0.json"},
        {"spdx_license_key": "LicenseRef-Private", "category": "Permissive", "json": "private.json"},
        {"spdx_license_key": "Odd-1.0", "category": "Unstated License", "json": "odd-1.0.json"},
        {"spdx_license_key": "Bad-1.0", "category": "Permissive", "json": "../bad.json"},
        {
            "spdx_license_key": "Special-exception",
            "category": "Permissive",
            "json": "exception.json",
            "is_exception": True,
        },
    ]
).encode("utf8")


class TestScanCodeLookup(TestCase):
    def test_lookup_is_opt_in_exact_and_cached_for_a_report(self):
        policy = LicenceAssessmentPolicy.from_config()
        with patch("continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen") as fetch:
            fetch.return_value = BytesIO(SCANCODE_INDEX)
            assessor = LicenceAssessor(policy, lookup_scancode=True)
            self.assertEqual(assessor.assess("BSD-3-Clause", "MIT").status, LicenceAssessment.ALLOW)
            fetch.assert_not_called()
            permissive = assessor.assess("BSD-3-Clause", "Zlib")
            limited = assessor.assess("BSD-3-Clause", "EPL-2.0")
            unresolved = assessor.assess("BSD-3-Clause", "Odd-1.0")
            project_lookup = assessor.assess("Zlib", "MIT")
            private = assessor.assess("BSD-3-Clause", "LicenseRef-Private")
            missing = assessor.assess("BSD-3-Clause", "Unknown")

        fetch.assert_called_once_with("https://scancode-licensedb.aboutcode.org/index.json", timeout=5)
        self.assertEqual(permissive.status, LicenceAssessment.ALLOW)
        self.assertEqual(permissive.rule, "permissive-dependency")
        self.assertEqual(permissive.scancode_licences[0].url, "https://scancode-licensedb.aboutcode.org/zlib.json")
        self.assertIn("ScanCode LicenseDB", permissive.reason)
        self.assertEqual(limited.status, LicenceAssessment.REVIEW)
        self.assertEqual(unresolved.status, LicenceAssessment.UNKNOWN)
        self.assertEqual(unresolved.scancode_licences[0].category, "Unstated License")
        self.assertEqual(project_lookup.status, LicenceAssessment.ALLOW)
        self.assertEqual(project_lookup.scancode_licences[0].identifier, "Zlib")
        self.assertEqual(private.status, LicenceAssessment.REVIEW)
        self.assertFalse(private.scancode_licences)
        self.assertEqual(missing.status, LicenceAssessment.UNKNOWN)
        self.assertFalse(missing.scancode_licences)

    def test_without_flag_does_not_contact_licensedb(self):
        with patch("continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen") as fetch:
            assessor = LicenceAssessor(LicenceAssessmentPolicy.from_config())
            result = assessor.assess("BSD-3-Clause", "Zlib")
        fetch.assert_not_called()
        self.assertEqual(result.status, LicenceAssessment.UNKNOWN)
        self.assertFalse(result.scancode_licences)

    def test_missing_directional_rule_stays_review_even_when_metadata_is_found(self):
        policy = LicenceAssessmentPolicy(
            {
                "schema_version": 1,
                "classifications": {"BSD-3-Clause": "PERMISSIVE", "Zlib": "PERMISSIVE"},
                "scancode_categories": {"Permissive": "PERMISSIVE"},
            }
        )
        with patch(
            "continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen", return_value=BytesIO(SCANCODE_INDEX)
        ):
            result = LicenceAssessor(policy, lookup_scancode=True).assess("BSD-3-Clause", "Zlib")
        self.assertEqual(result.status, LicenceAssessment.REVIEW)
        self.assertEqual(result.rule, "directional-rule-missing")
        self.assertTrue(result.scancode_licences)

    def test_failure_and_untrusted_index_entries_do_not_create_false_allows(self):
        with patch(
            "continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen", side_effect=URLError("offline")
        ) as fetch:
            assessor = LicenceAssessor(LicenceAssessmentPolicy.from_config(), lookup_scancode=True)
            self.assertEqual(assessor.assess("BSD-3-Clause", "Zlib").status, LicenceAssessment.UNKNOWN)
            self.assertEqual(assessor.assess("BSD-3-Clause", "EPL-2.0").status, LicenceAssessment.UNKNOWN)
        fetch.assert_called_once()
        with patch(
            "continuous_delivery_scripts.spdx_report.scancode_licence_db.urlopen", return_value=BytesIO(SCANCODE_INDEX)
        ):
            lookup = ScanCodeLicenceDB()
            self.assertIsNone(lookup.find("LicenseRef-Private"))
            self.assertIsNone(lookup.find("Bad-1.0"))
            self.assertIsNone(lookup.find("Special-exception"))
