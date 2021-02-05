#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import os
import re
from unittest import TestCase

from pathlib import Path

from continuous_delivery_scripts.utils.filesystem_helpers import (
    TemporaryDirectory,
    find_file_in_tree,
    cd,
    scan_file_for_pattern,
    match_pattern,
    should_exclude_path,
    list_all_files,
)
from continuous_delivery_scripts.spdx_report.spdx_helpers import SPDX_LICENCE_IDENTIFIER_PATTERN


class TestFilesystemHelpers(TestCase):
    def test_temporary_directory(self):
        temp_dir_path = None
        temp_file_path = None
        with TemporaryDirectory() as temp_dir:
            self.assertIsNotNone(temp_dir)
            self.assertTrue(temp_dir.exists())
            temp_dir_path = temp_dir
            temp_file = temp_dir.joinpath("test.test")
            temp_file_path = temp_file
            self.assertFalse(temp_file.exists())
            temp_file.touch()
            self.assertTrue(temp_file.exists())
        self.assertIsNotNone(temp_dir_path)
        self.assertIsNotNone(temp_file_path)
        self.assertFalse(temp_file_path.exists())
        self.assertFalse(temp_dir_path.exists())

    def test_multiple_temporary_dir_cleanup(self):
        tmp = TemporaryDirectory()
        self.assertTrue(tmp.path.exists())
        tmp.cleanup()
        self.assertFalse(tmp.path.exists())
        tmp.cleanup()
        self.assertFalse(tmp.path.exists())

    def test_cd(self):
        with TemporaryDirectory() as temp_dir:
            self.assertNotEqual(Path(os.getcwd()), temp_dir)
            with cd(temp_dir):
                self.assertEqual(Path(os.getcwd()), temp_dir)
            self.assertNotEqual(Path(os.getcwd()), temp_dir)

    def test_find_file_up_the_tree(self):
        filename = "test.test"
        with TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir).joinpath(filename)
            temp_file.touch()
            child_dir = temp_dir
            for i in range(0, 10):
                child_dir = child_dir.joinpath(f"test{str(i)}")
                os.makedirs(child_dir)
            with cd(child_dir):
                self.assertEqual(temp_file, Path(find_file_in_tree(filename, starting_point=os.getcwd(), top=True)))

    def test_find_file_down_the_tree(self):
        filename = "test.test"
        with TemporaryDirectory() as temp_dir:
            child_dir = temp_dir
            for i in range(0, 10):
                child_dir = child_dir.joinpath(f"test{str(i)}")
                os.makedirs(child_dir)
            temp_file = Path(child_dir).joinpath(filename)
            temp_file.touch()
            with cd(str(temp_dir)):
                self.assertEqual(temp_file, Path(find_file_in_tree(filename, starting_point=os.getcwd(), top=False)))

    def test_matches_pattern(self):
        self.assertTrue(match_pattern(Path("/test/test1/a_test.test"), "*.test"))
        self.assertTrue(match_pattern(Path("/test/test1/a_test.test"), "a_test*"))
        self.assertTrue(match_pattern(Path("/test/test1"), "**/test1"))
        self.assertTrue(match_pattern(Path("/test/test1/a_test.test"), "**/test1/*"))
        self.assertTrue(match_pattern(Path("/test/test1/test2/a_test.test"), "**/test2/*"))
        self.assertTrue(match_pattern(Path("/test/test1/test2/a_test.test"), "**/test2/*.test"))
        self.assertTrue(match_pattern(Path("/test/test1/a_test.test"), "/test/**"))
        self.assertTrue(match_pattern(Path("/test/more.test1/a_test.test"), "**/*.test1/**"))
        self.assertFalse(match_pattern(Path("/test/more.test1/a_test.test"), "**/test1/**"))
        self.assertFalse(match_pattern(Path("/test/test1/test2/a_test.txt"), "*.test"))
        self.assertFalse(match_pattern(Path("/test/test1/test2/a_test.txt"), "*.ignore"))
        self.assertFalse(match_pattern(Path("/test/test1/test2/a_test.txt"), "**/test3/*"))
        self.assertFalse(match_pattern(Path("/test/test1/test2/a_test.txt"), "**/test2/*.test"))

    def test_should_exclude_path(self):
        self.assertTrue(should_exclude_path(Path("/test/test1/test2/a_test.test"), ["*.ignore", "*.test"]))
        self.assertFalse(should_exclude_path(Path("/test/test1/test2/a_test.txt"), ["*.ignore", "*.test"]))
        self.assertTrue(should_exclude_path(Path("/test/test1/test2/a_test.test"), ["*.ignore", "**/test1/**"]))
        self.assertFalse(should_exclude_path(Path("/test/test3/test2/a_test.test"), ["*.ignore", "**/test1/**"]))
        self.assertFalse(should_exclude_path(Path("/test/more.test1/test2/a_test.test"), ["*.ignore", "**/test1/**"]))
        self.assertTrue(should_exclude_path(Path("/test/more.test1/test2/a_test.test"), ["*.ignore", "**/*.test1/**"]))

    def test_list_files(self):
        self.assertListEqual(
            sorted([p.name for p in list_all_files(Path(__file__).parent.joinpath("fixtures"))]),
            ["file_with_patterns.txt", "test.test", "test.txt"],
        )

        def ignore1(p: Path) -> bool:
            return should_exclude_path(p, ["*.txt", "*.test"])

        self.assertListEqual([p.name for p in list_all_files(Path(__file__).parent.joinpath("fixtures"), ignore1)], [])

        def ignore2(p: Path) -> bool:
            return should_exclude_path(p, ["**/test_directory/**", "*.tmp"])

        self.assertListEqual(
            [p.name for p in list_all_files(Path(__file__).parent.joinpath("fixtures"), ignore2)],
            ["file_with_patterns.txt"],
        )

    def test_file_scanner(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "file_with_patterns.txt")
        pattern1 = re.compile(SPDX_LICENCE_IDENTIFIER_PATTERN, re.MULTILINE)
        match = scan_file_for_pattern(test_file, pattern1)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "EPL-1.0+ AND Apache-2.0 AND (MIT OR BSD-only) WITH   Classpath-exception-2.0")
        pattern2 = re.compile(r"^startpattern:$[\r\n]+([\w\n\r]*)^endpattern$", re.MULTILINE)
        match = scan_file_for_pattern(test_file, pattern2)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.group(1),
            """some
value
over
multiple
lines
""",
        )
