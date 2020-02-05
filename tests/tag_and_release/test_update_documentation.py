"""Tests for mbed_tools_ci_scripts.tag_and_release documentation update functions."""
import os
from unittest import mock, TestCase

import pathlib
from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci_scripts.tag_and_release import (
    _update_documentation,
)


class TestAddNewDocumentation(TestCase):
    @mock.patch("mbed_tools_ci_scripts.generate_docs._call_pdoc")
    @mock.patch(
        "mbed_tools_ci_scripts.tag_and_release._get_documentation_config")
    def test_update_docs(self, _get_documentation_config, _call_pdoc):
        with Patcher() as patcher:
            module_name = "module_name"
            docs_dir = pathlib.Path("docs")

            _get_documentation_config.return_value = docs_dir, module_name

            def mocked_generate_docs(output_directory, module):
                # Creating some fake files in a same way as Pdoc
                if not output_directory.exists():
                    patcher.fs.create_dir(output_directory)
                docs_contents_dir = output_directory.joinpath(module)
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("docs_file.html")),
                    contents="This is some documentation."
                )
                # check that it moves subdirectories too
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("sub_dir",
                                                   "docs_file.html")),
                    contents="This is some more documentation."
                )

            _call_pdoc.side_effect = mocked_generate_docs

            patcher.fs.create_file(
                str(docs_dir.joinpath("old_docs_file.html")),
                contents="This is some old documentation."
            )
            self.assertTrue(docs_dir.joinpath("old_docs_file.html").exists())

            _update_documentation()

            # Check that old documentation in the output directory has been removed
            self.assertFalse(docs_dir.joinpath("old_docs_file.html").exists())
            # Check that module name directory is not present in the output directory
            print(os.listdir(docs_dir))
            self.assertTrue(docs_dir.joinpath("docs_file.html").is_file())
            self.assertTrue(
                docs_dir.joinpath("sub_dir", "docs_file.html").is_file())
            self.assertFalse(docs_dir.joinpath(module_name).exists())
