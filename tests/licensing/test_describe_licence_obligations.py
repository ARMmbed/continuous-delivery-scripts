#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from unittest.mock import patch

from continuous_delivery_scripts.spdx_report.project_licensing import ChooseALicenseMetadata
from continuous_delivery_scripts.spdx_report.project_licensing import describe_licence_obligations


class TestDescribeLicenceObligations(unittest.TestCase):
    def test_rejects_compound_licence_expression(self):
        with self.assertRaisesRegex(ValueError, "does not cover compound licence expressions"):
            describe_licence_obligations("MIT OR Apache-2.0")

    def test_describes_proprietary_licence(self):
        description = describe_licence_obligations("LicenseRef-Proprietary")
        self.assertIn("This project uses a proprietary licence.", description)
        self.assertIn("author must provide the full licence text", description)

    @patch(
        "continuous_delivery_scripts.spdx_report.project_licensing.fetch_choosealicense_metadata",
        return_value=ChooseALicenseMetadata(
            summary="A permissive licence with notice obligations.",
            permissions=("Commercial use", "Modification"),
            conditions=("License and copyright notice", "State changes"),
            limitations=("Liability",),
            text=None,
            url="https://choosealicense.com/licenses/apache-2.0/",
        ),
    )
    @patch(
        "continuous_delivery_scripts.spdx_report.project_licensing.fetch_osadl_obligations",
        return_value="USE CASE Source code delivery\n\tYOU MUST Provide License text",
    )
    @patch(
        "continuous_delivery_scripts.spdx_report.project_licensing.fetch_spdx_licence_details",
        return_value={"name": "Apache License 2.0", "isOsiApproved": True},
    )
    def test_combines_spdx_choosealicense_and_osadl_data(self, *_args):
        description = describe_licence_obligations("Apache-2.0")
        self.assertIn("SPDX identifier: Apache-2.0", description)
        self.assertIn("Name: Apache License 2.0", description)
        self.assertIn("OSI approved: yes", description)
        self.assertIn("Permissions:\n- Commercial use\n- Modification", description)
        self.assertIn("Conditions:\n- License and copyright notice\n- State changes", description)
        self.assertIn("OSADL obligations:\nUSE CASE Source code delivery", description)
