"""Tests for mbed_tools_ci.tag_and_release documentation update functions."""
import pathlib
from unittest import mock, TestCase
from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci.tag_and_release import (
    _remove_old_documentation,
    _add_new_documentation,
)
from mbed_tools_ci.utils.git_helpers import GitWrapper


class TestRemoveOldDocumentation(TestCase):
    """Test removing the docs directory."""
    def test_remove_old_documentation_if_present(self):
        """If existing docs dir with contents is present, it removes it."""
        with Patcher() as patcher:
            fake_docs_dir = pathlib.Path("imaginary/docs/folder")
            patcher.fs.create_file(
                str(fake_docs_dir.joinpath('some_docs_file.html')),
                contents='This is some old documentation.'
            )
            # check that it removes subdirectories too
            patcher.fs.create_file(
                str(fake_docs_dir.joinpath("sub_dir", "another_docs_file.html")),
                contents='This is some more documentation.'
            )
            fake_git = mock.Mock(spec_set=GitWrapper)
            _remove_old_documentation(fake_git, fake_docs_dir)

            self.assertFalse(fake_docs_dir.is_dir())
            fake_git.add.assert_called_with(str(fake_docs_dir))

    def test_remove_old_documentation_no_error_if_not_present(self):
        """If there is no existing docs dir, it doesn't error."""
        fake_docs_dir = pathlib.Path("imaginary/docs/folder")

        fake_git = mock.Mock(spec_set=GitWrapper)
        _remove_old_documentation(fake_git, fake_docs_dir)

        self.assertFalse(pathlib.Path(fake_docs_dir).is_file())
        fake_git.add.assert_not_called()


class TestAddNewDocumentation(TestCase):
    """Test moving documentation from temp directory to docs directory."""
    def test_add_docs(self):
        """Moves docs from temp dir to final destination dir."""
        with Patcher() as patcher:
            module_name = "module_name"
            fake_temp_docs_dir = pathlib.Path("temp/docs/folder").joinpath(module_name)
            fake_docs_dir = pathlib.Path("docs/folder")

            patcher.fs.create_file(
                str(fake_temp_docs_dir.joinpath("docs_file.html")),
                contents="This is some old documentation."
            )
            # check that it moves subdirectories too
            patcher.fs.create_file(
                str(fake_temp_docs_dir.joinpath("sub_dir", "docs_file.html")),
                contents="This is some more documentation."
            )
            fake_git = mock.Mock(spec_set=GitWrapper)
            _add_new_documentation(fake_git, fake_temp_docs_dir, fake_docs_dir)

            # Check that module name directory has been removed from path in transfer
            self.assertTrue(fake_docs_dir.joinpath("docs_file.html").is_file())
            self.assertTrue(fake_docs_dir.joinpath("sub_dir", "docs_file.html").is_file())
            fake_git.add.assert_called_with(str(fake_docs_dir))
