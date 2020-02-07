import os
from unittest import TestCase

from pathlib import Path

from mbed_tools_ci_scripts.utils.filesystem_helpers import TemporaryDirectory, find_file_in_tree, cd


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
