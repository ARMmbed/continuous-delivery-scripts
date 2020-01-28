"""Tests for mbed_tools_ci.assert_news.NewsFileValidator."""
from unittest import mock, TestCase
from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci.assert_news import (
    NewsFileValidator,
    NEWS_FILE_NAME_REGEX,
)


class TestValidateFileName(TestCase):
    """Tests for the NewsFileValidator.validate_file_name method."""

    def test_raises_if_file_name_is_not_valid(self):
        """Given an invalid file name, it raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            NewsFileValidator("imaginary/path/to/file.tar.gz").validate_file_name()

        expected_error_message = (
            f'Incorrect news file name "file.tar.gz".'
            f' It doesn\'t match the following regex: "{NEWS_FILE_NAME_REGEX}".'
        )
        self.assertEqual(str(cm.exception), expected_error_message)

    def test_does_nothing_if_name_is_valid(self):
        """Given a valid file name, it does nothing."""
        file_path = "some/other/20201112.feature"

        NewsFileValidator(file_path).validate_file_name()


class TestValidateFileContent(TestCase):
    """Tests for the NewsFileValidator.validate_file_content method."""

    def test_raises_if_file_is_empty(self):
        """When a news file is empty, it raises ValueError."""
        with Patcher() as patcher:
            file_path = "/foo/bar.txt"
            patcher.fs.create_file(file_path, contents="")

            with self.assertRaises(ValueError) as cm:
                NewsFileValidator(file_path).validate_file_contents()

            expected_error_message = f'Empty news file "bar.txt".'
            self.assertEqual(str(cm.exception), expected_error_message)

    def test_raises_if_file_has_too_many_lines(self):
        """When a news file contains more than one line, it raises ValueError."""
        with Patcher() as patcher:
            file_path = "/foo/baz.txt"
            patcher.fs.create_file(file_path, contents="foo\nbar")

            with self.assertRaises(ValueError) as cm:
                NewsFileValidator(file_path).validate_file_contents()

            expected_error_message = f'News file "baz.txt" contains more than one line.'
            self.assertEqual(str(cm.exception), expected_error_message)

    def test_does_nothing_if_file_has_valid_contents(self):
        """Given a valid file it does nothing."""
        with Patcher() as patcher:
            file_path = "/hat/boat.zip"
            patcher.fs.create_file(file_path, contents="foo")

            NewsFileValidator(file_path).validate_file_contents()


class TestValidate(TestCase):
    """Tests for the NewsFileValidator.validate method."""

    def test_calls_all_validators(self):
        """It calls all validators."""
        validator = NewsFileValidator("/some/file")
        validator.validate_file_name = mock.Mock()
        validator.validate_file_contents = mock.Mock()

        validator.validate()

        validator.validate_file_name.assert_called_once()
        validator.validate_file_contents.assert_called_once()
