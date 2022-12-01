#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import mock, TestCase
from pyfakefs.fake_filesystem_unittest import Patcher

from continuous_delivery_scripts.assert_news import NEWS_FILE_NAME_REGEX, NewsFileValidator, validate_news_file


class TestValidateFileName(TestCase):
    def test_raises_if_file_name_is_not_valid(self):
        with self.assertRaises(ValueError) as cm:
            NewsFileValidator("/imaginary/path/to/file.tar.gz").validate_file_name()

        expected_error_message = (
            f'Incorrect news file name "file.tar.gz".'
            f' It doesn\'t match the following regex: "{NEWS_FILE_NAME_REGEX}".'
        )
        self.assertEqual(str(cm.exception), expected_error_message)

    def test_does_nothing_if_name_is_valid(self):
        file_path = "/some/other/20201112.feature"

        NewsFileValidator(file_path).validate_file_name()


class TestValidateFileContent(TestCase):
    def test_raises_if_file_is_empty(self):
        with Patcher() as patcher:
            file_path = "/foo/bar.txt"
            patcher.fs.create_file(file_path, contents="")

            with self.assertRaises(ValueError) as cm:
                NewsFileValidator(file_path).validate_file_contents()

            expected_error_message = 'Empty news file "bar.txt".'
            self.assertEqual(str(cm.exception), expected_error_message)

    def test_raises_if_file_has_too_many_lines(self):
        with Patcher() as patcher:
            file_path = "/foo/baz.txt"
            patcher.fs.create_file(file_path, contents="foo\nbar")

            with self.assertRaises(ValueError) as cm:
                NewsFileValidator(file_path).validate_file_contents()

            expected_error_message = 'News file "baz.txt" contains more than one line.'
            self.assertEqual(str(cm.exception), expected_error_message)

    def test_does_nothing_if_file_has_valid_contents(self):
        with Patcher() as patcher:
            file_path = "/hat/boat.zip"
            patcher.fs.create_file(file_path, contents="foo")

            NewsFileValidator(file_path).validate_file_contents()


class TestValidate(TestCase):
    def test_calls_all_validators(self):
        validator = NewsFileValidator("/some/file")
        validator.validate_file_name = mock.Mock()
        validator.validate_file_contents = mock.Mock()

        validator.validate()

        validator.validate_file_name.assert_called_once()
        validator.validate_file_contents.assert_called_once()


class TestValidateNewsFile(TestCase):
    @mock.patch("continuous_delivery_scripts.assert_news.NewsFileValidator")
    def test_constructs_validator_and_calls_it(self, FakeNewsFileValidator):
        instance = mock.Mock(spec_set=NewsFileValidator)
        FakeNewsFileValidator.return_value = instance

        file_path = "some/path"
        validate_news_file(file_path)

        FakeNewsFileValidator.assert_called_once_with(file_path)
        instance.validate.assert_called_once()
