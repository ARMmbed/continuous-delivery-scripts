#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import os
import unittest
from unittest.mock import patch

from datetime import datetime

from continuous_delivery_scripts.license_files import (
    _normalise_markdown_copyright_spacing,
    _to_copyright_date_string,
)
from continuous_delivery_scripts.license_files import add_licence_header
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable


class TestLicenceHeader(unittest.TestCase):
    def test_markdown_copyright_normalisation_skips_directories(self):
        with TemporaryDirectory() as directory:
            markdown_directory = directory / "directory.md"
            markdown_directory.mkdir()
            source = markdown_directory / "README.md"
            content = b"<!-- Copyright -->\n# Heading\n"
            source.write_bytes(content)

            _normalise_markdown_copyright_spacing(directory)

            self.assertTrue(markdown_directory.is_dir())
            self.assertEqual(b"<!-- Copyright -->\n\n# Heading\n", source.read_bytes())

    def test_markdown_copyright_normalisation_skips_unwritable_files(self):
        with TemporaryDirectory() as directory:
            source = directory / "README.md"
            content = b"<!-- Copyright -->\n# Heading\n"
            source.write_bytes(content)

            with patch("continuous_delivery_scripts.license_files.os.access", return_value=False) as access:
                with patch.object(type(source), "write_bytes", side_effect=PermissionError) as write_bytes:
                    _normalise_markdown_copyright_spacing(directory)

            access.assert_called_once_with(source, os.W_OK)
            write_bytes.assert_not_called()
            self.assertEqual(content, source.read_bytes())

    def test_markdown_copyright_spacing_after_header_insertion(self):
        for newline in (b"\n", b"\r\n"):
            for existing_notice in (False, True):
                with self.subTest(newline=newline, existing_notice=existing_notice), TemporaryDirectory() as directory:
                    source = directory / "README.md"
                    body = b"# Heading\n\nUnrelated text.\n\n<!-- Body comment -->\nNext paragraph.\n"
                    notice = (
                        b"<!--\nCopyright (C) 2020 Arm Limited\nSPDX-License-Identifier: Apache-2.0\n-->\n"
                        if existing_notice
                        else b""
                    )
                    source.write_bytes((notice + body).replace(b"\n", newline))

                    add_licence_header(0, directory)
                    content = source.read_bytes()
                    header, closing, remainder = content.partition(b"-->")
                    self.assertIn(b"Copyright (C)", header)
                    self.assertIn(b"SPDX-License-Identifier: Apache-2.0", header)
                    self.assertEqual(b"-->", closing)
                    # licenseheaders itself canonicalises line endings to LF.
                    self.assertEqual(b"\n\n" + body, remainder)

                    add_licence_header(0, directory)
                    self.assertEqual(content, source.read_bytes())

    def test_markdown_copyright_normalisation_preserves_body_bytes(self):
        for newline in (b"\n", b"\r\n"):
            for blank_lines in (0, 1, 2):
                with self.subTest(newline=newline, blank_lines=blank_lines), TemporaryDirectory() as directory:
                    source = directory / "nested" / "guide.md"
                    source.parent.mkdir()
                    header = newline.join((b"<!--", b"Copyright (C) 2020 Arm Limited", b"-->", b""))
                    body = b"# Heading\n\nText with trailing spaces.  \n<!-- Copyright in body -->\nUnchanged."
                    body = body.replace(b"\n", newline)
                    source.write_bytes(header + newline * blank_lines + body)

                    _normalise_markdown_copyright_spacing(directory)
                    expected = header + newline * max(1, blank_lines) + body
                    self.assertEqual(expected, source.read_bytes())

                    with patch.object(type(source), "write_bytes") as write_bytes:
                        _normalise_markdown_copyright_spacing(directory)
                    write_bytes.assert_not_called()
                    self.assertEqual(expected, source.read_bytes())

    def test_markdown_copyright_normalisation_leaves_unrelated_content_unchanged(self):
        contents = (
            b"# Heading\n<!-- Copyright (C) 2020 Arm Limited -->\nBody\n",
            b"<!-- An unrelated comment -->\n# Heading\n<!-- Copyright -->\nBody\n",
            b"<!-- Copyright without a closing comment\n",
            b"<!-- Copyright -->\n",
            b"<!-- Copyright -->",
        )
        with TemporaryDirectory() as directory:
            for content in contents:
                with self.subTest(content=content):
                    source = directory / "README.md"
                    source.write_bytes(content)
                    _normalise_markdown_copyright_spacing(directory)
                    self.assertEqual(content, source.read_bytes())

            source = directory / "example.html"
            content = b"<!-- Copyright -->\n<p>Not Markdown</p>\n"
            source.write_bytes(content)
            _normalise_markdown_copyright_spacing(directory)
            self.assertEqual(content, source.read_bytes())

    def test_proprietary_header_uses_spdx_licence_reference(self):
        get_value = configuration.get_value
        with TemporaryDirectory() as directory, patch.object(
            configuration,
            "get_value",
            side_effect=lambda key: (
                "proprietary" if key == ConfigurationVariable.FILE_LICENCE_IDENTIFIER else get_value(key)
            ),
        ):
            source = directory / "example.java"
            source.write_text("class Example {}\n", encoding="utf8")
            add_licence_header(0, directory)
            header = source.read_text(encoding="utf8")

        self.assertIn("SPDX-License-Identifier: LicenseRef-Proprietary", header)
        self.assertNotIn("SPDX-License-Identifier: proprietary", header)

    def test_copyright_dates(self):
        self.assertEqual("2020", _to_copyright_date_string(2020, 2020))
        self.assertEqual("2020-2021", _to_copyright_date_string(2020, 2021))
        this_year = datetime.now().year
        self.assertEqual(str(this_year), _to_copyright_date_string(this_year, this_year))

    def test_add_licence_header(self):
        with TemporaryDirectory() as testDir:
            test_filepath = testDir.joinpath("test.java")
            test_filepath.touch()
            file_content = []
            with open(test_filepath, "r", encoding="utf-8") as test_file:
                file_content = test_file.readlines()
            self.assertTrue(len(file_content) == 0)
            add_licence_header(3, test_filepath.parent)
            with open(test_filepath, "r", encoding="utf-8") as test_file:
                file_content = test_file.readlines()
                print(file_content)
            self.assertFalse(len(file_content) == 0)
