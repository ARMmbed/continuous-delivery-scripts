#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import pathlib
from pyfakefs.fake_filesystem_unittest import Patcher
from unittest import TestCase, mock
from datetime import datetime

from mbed_tools_ci_scripts.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci_scripts.create_news_file import NewsType, create_news_file, determine_news_file_path, _write_file


class TestCreateNewsFile(TestCase):
    @mock.patch("mbed_tools_ci_scripts.create_news_file.determine_news_file_path")
    @mock.patch("mbed_tools_ci_scripts.create_news_file._write_file")
    def test_creates_a_file_with_available_file_name_and_returns_its_path(self, _write_file, determine_news_file_path):
        news_file_path = pathlib.Path("some/1234501.feature")
        determine_news_file_path.return_value = news_file_path
        news_text = "Cool feature"
        news_type = NewsType.feature

        file_path = create_news_file(news_text, news_type)

        self.assertEqual(file_path, news_file_path)
        determine_news_file_path.assert_called_once_with(news_type)
        _write_file.assert_called_once_with(file_path, news_text)


class TestDetermineNewsFilePath(TestCase):
    def test_finds_first_available_file_path_in_news_dir(self):
        news_dir = configuration.get_value(ConfigurationVariable.NEWS_DIR)
        news_file_name_today = datetime.now().strftime("%Y%m%d")
        news_file_path_today = str(pathlib.Path(news_dir, news_file_name_today))

        for news_type in NewsType:
            with self.subTest(f"It determines available file path for {news_type}."):
                with Patcher() as patcher:
                    patcher.fs.create_file(f"{news_file_path_today}.{news_type.name}")
                    patcher.fs.create_file(f"{news_file_path_today}01.{news_type.name}")

                    file_path = determine_news_file_path(news_type)

                    self.assertEqual(file_path, pathlib.Path(news_dir, f"{news_file_name_today}02.{news_type.name}"))


class TestWriteFile(TestCase):
    def test_writes_files_in_nested_directories(self):
        with Patcher():
            file_path = "/some/directory/file.txt"
            path = pathlib.Path(file_path)
            contents = "woohoo"
            _write_file(path, contents)

            self.assertEqual(path.read_text(), contents)
