#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from mbed_tools_ci_scripts.spdx_report.spdx_helpers import determine_licence_compound


class TestSpdxHelpers(TestCase):
    def test_licences_evaluation(self):
        self.assertEqual(
            determine_licence_compound("Apache-2.0", ["Apache-2.0", "Apache-2.0", "BSD OR MIT"]),
            "Apache-2.0 AND (BSD OR MIT)",
        )
