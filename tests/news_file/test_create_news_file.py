#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import pathlib
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from continuous_delivery_scripts.create_news_file import NEWS_DIR
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.news_file import (
    NewsType,
    determine_news_file_path,
    determine_basic_new_news_file_name,
    create_news_file,
    _write_file,
)


class TestCreateNewsFile(TestCase):
    @mock.patch("continuous_delivery_scripts.utils.news_file.determine_news_file_path")
    @mock.patch("continuous_delivery_scripts.utils.news_file._write_file")
    def test_creates_a_file_with_available_file_name_and_returns_its_path(self, _write_file, determine_news_file_path):
        news_file_path = pathlib.Path("some/1234501.feature")
        determine_news_file_path.return_value = news_file_path
        news_text = "Cool feature"
        news_type = NewsType.feature

        file_path = create_news_file(NEWS_DIR, None, news_text, news_type)

        self.assertEqual(file_path, news_file_path)
        determine_news_file_path.assert_called_once_with(NEWS_DIR, None, news_type)
        _write_file.assert_called_once_with(file_path, news_text)

    @mock.patch("continuous_delivery_scripts.utils.news_file.determine_news_file_path")
    @mock.patch("continuous_delivery_scripts.utils.news_file._write_file")
    def test_creates_a_file_with_message_type_string(self, _write_file, determine_news_file_path):
        news_file_path = pathlib.Path("some/1234501.feature")
        determine_news_file_path.return_value = news_file_path
        news_text = "Cool feature"
        news_type = NewsType.feature

        file_path = create_news_file(NEWS_DIR, None, news_text, news_type.name)

        self.assertEqual(file_path, news_file_path)
        determine_news_file_path.assert_called_once_with(NEWS_DIR, None, news_type)
        _write_file.assert_called_once_with(file_path, news_text)

    @mock.patch("continuous_delivery_scripts.utils.news_file.determine_basic_new_news_file_name")
    @mock.patch("continuous_delivery_scripts.utils.news_file._write_file")
    def test_creates_a_file_with_news_reference(self, _write_file, determine_basic_new_news_file_name):
        determine_basic_new_news_file_name.return_value = "1234501.feature"
        news_text = "Cool feature"
        news_type = NewsType.feature
        ref = "123456"
        expected_file_path = pathlib.Path(NEWS_DIR, f"{ref}.feature")
        file_path = create_news_file(NEWS_DIR, ref, news_text, news_type.name)

        self.assertEqual(file_path, expected_file_path)
        _write_file.assert_called_once_with(file_path, news_text)

    @mock.patch("continuous_delivery_scripts.utils.news_file.determine_basic_new_news_file_name")
    @mock.patch("continuous_delivery_scripts.utils.news_file._write_file")
    def test_creates_a_file_without_news_reference(self, _write_file, determine_basic_new_news_file_name):
        expected_file_name = "1234501"
        determine_basic_new_news_file_name.return_value = expected_file_name
        news_text = "Cool feature"
        news_type = NewsType.feature

        file_path = create_news_file(NEWS_DIR, None, news_text, news_type.name)

        self.assertEqual(file_path, pathlib.Path(NEWS_DIR, f"{expected_file_name}.feature"))
        _write_file.assert_called_once_with(file_path, news_text)


class TestDetermineNewsFilePath(TestCase):
    def test_finds_first_available_file_path_in_news_dir(self):
        news_dir = configuration.get_value(ConfigurationVariable.NEWS_DIR)
        news_file_name_today = determine_basic_new_news_file_name()
        news_file_path_today = str(pathlib.Path(news_dir, news_file_name_today))

        for news_type in NewsType:
            with self.subTest(f"It determines available file path for {news_type}."):
                with TemporaryDirectory() as tmp_dir:
                    pathlib.Path(tmp_dir, f"{news_file_path_today}.{news_type.name}").touch()
                    pathlib.Path(tmp_dir, f"{news_file_path_today}01.{news_type.name}").touch()

                    file_path = determine_news_file_path(NEWS_DIR, None, news_type)

                    self.assertEqual(file_path, pathlib.Path(news_dir, f"{news_file_name_today}02.{news_type.name}"))


class TestWriteFile(TestCase):
    def test_writes_files_in_nested_directories(self):
        with TemporaryDirectory() as tmp_dir:
            dir_path = pathlib.Path(tmp_dir, "some", "dir")
            dir_path.mkdir(parents=True)
            file_path = dir_path / "file.txt"
            file_path.touch()
            contents = "woohoo"
            _write_file(file_path, contents)

            self.assertEqual(file_path.read_text(), f"{contents}\n")

    def test_skips_adding_newline_if_already_exists(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = pathlib.Path(tmp_dir, "file.txt")
            contents = "woohoo\n"
            _write_file(file_path, contents)

            self.assertEqual(file_path.read_text(), contents)
