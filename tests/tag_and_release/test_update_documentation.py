"""Tests for mbed_tools_ci_scripts.tag_and_release documentation update functions."""
import pathlib
from unittest import mock, TestCase
from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci_scripts.tag_and_release import (
    _update_documentation,
)


class TestAddNewDocumentation(TestCase):
    @mock.patch("mbed_tools_ci_scripts.tag_and_release.TemporaryDirectory")
    @mock.patch("mbed_tools_ci_scripts.tag_and_release._get_documentation_paths")
    def test_update_docs(self, _get_documentation_paths, TemporaryDictionary):
        with Patcher() as patcher:
            temp_dir = pathlib.Path("temp")
            TemporaryDictionary.return_value = temp_dir

            module_name = "module_name"
            docs_dir = pathlib.Path("docs")
            docs_contents_dir = docs_dir.joinpath(module_name)
            _get_documentation_paths.return_value = docs_dir, docs_contents_dir

            patcher.fs.create_file(
                str(docs_contents_dir.joinpath("docs_file.html")),
                contents="This is some old documentation."
            )
            # check that it moves subdirectories too
            patcher.fs.create_file(
                str(docs_contents_dir.joinpath("sub_dir", "docs_file.html")),
                contents="This is some more documentation."
            )
            _update_documentation()

            # Check that module name directory has been removed from path in transfer
            self.assertTrue(docs_dir.joinpath("docs_file.html").is_file())
            self.assertTrue(docs_dir.joinpath("sub_dir", "docs_file.html").is_file())
            self.assertFalse(docs_contents_dir.is_dir())
