#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from io import StringIO
from unittest.mock import patch

from continuous_delivery_scripts.describe_licence_obligations import main


class TestDescribeLicenceObligationsCli(unittest.TestCase):
    def test_uses_project_configuration_identifier(self):
        with patch("sys.argv", ["cd-describe-licence-obligations"]), patch(
            "continuous_delivery_scripts.describe_licence_obligations.describe_licence_obligations",
            return_value="SPDX identifier: Apache-2.0\n",
        ) as describe, patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(main(), 0)

        describe.assert_called_once_with()
        self.assertEqual("SPDX identifier: Apache-2.0\n", output.getvalue())
