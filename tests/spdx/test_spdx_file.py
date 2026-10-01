#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase

from pathlib import Path
from tempfile import TemporaryDirectory

from continuous_delivery_scripts.spdx_report.spdx_file import determine_file_licence, determine_file_copyright_text
from continuous_delivery_scripts.spdx_report.spdx_helpers import list_project_files_for_licensing
from continuous_delivery_scripts.spdx_report.spdx_file import SpdxFile


class TestSpdxFile(TestCase):
    def test_file_with_proprietary_notice_has_licence_reference(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "main.go")
            source.write_text("// SPDX-License-Identifier: Proprietary\npackage main\n", encoding="utf8")

            self.assertEqual(SpdxFile(source, Path(directory), "MIT").licence, "LicenseRef-Proprietary")

    def test_generated_executable_is_excluded_from_source_licence_scan(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "main.go")
            source.write_text("package main\n", encoding="utf8")
            Path(directory, "main.exe").write_bytes(b"\x00\x01binary")

            self.assertEqual(list(list_project_files_for_licensing(Path(directory))), [source])

    def test_spdx_identifier_does_not_include_following_source_line(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "main.go")
            source.write_text("// SPDX-License-Identifier: MIT\npackage main\n", encoding="utf8")

            self.assertEqual(determine_file_licence(source), "MIT")

    def test_file_licence_scanner(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "file_with_patterns.txt")
        licence = determine_file_licence(test_file)
        self.assertIsNotNone(licence)
        self.assertEqual(licence, "Apache-2.0 AND EPL-1.0 AND (BSD OR MIT)")

    def test_file_copyright_scanner(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "file_with_patterns.txt")
        copyright = determine_file_copyright_text(test_file)
        self.assertIsNotNone(copyright)
        self.assertEqual(copyright, "Copyright (C) 2020 Arm Mbed. All rights reserved.")
