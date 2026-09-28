#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import pathlib
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from continuous_delivery_scripts.assert_news import MissingNewsFileError, main
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable
from continuous_delivery_scripts.utils.git_helpers import GitWrapper


class TestAssertNewsMain(TestCase):
    @mock.patch("continuous_delivery_scripts.assert_news._commit_news_file")
    @mock.patch("continuous_delivery_scripts.assert_news.generate_news_file")
    @mock.patch("continuous_delivery_scripts.assert_news.validate_news_files")
    @mock.patch("continuous_delivery_scripts.assert_news.ProjectTempClone")
    @mock.patch("continuous_delivery_scripts.assert_news.configuration.get_value")
    def test_generates_only_when_news_is_missing(self, get_value, temp_clone, validate_news_files, generate, commit):
        project_root = pathlib.Path("/original-project")
        get_value.side_effect = {
            ConfigurationVariable.PROJECT_ROOT: str(project_root),
            ConfigurationVariable.NEWS_DIR: str(project_root / "news"),
        }.get
        git = mock.Mock(spec_set=GitWrapper)
        git.root = pathlib.Path("/clone")
        git.is_current_branch_feature.return_value = True
        git.get_corresponding_path.return_value = pathlib.Path("/clone/news")
        temp_clone.return_value.__enter__.return_value = git
        validate_news_files.side_effect = MissingNewsFileError("News file missing")
        news_file = pathlib.Path("/clone/news/123.bugfix")
        generate.return_value = news_file

        with mock.patch("sys.argv", ["cd-assert-news", "-b", "dependabot/pip/example"]):
            with self.assertRaises(SystemExit) as cm:
                main()

        self.assertEqual(cm.exception.code, 1)
        validate_news_files.assert_called_once_with(git=git, news_dir="news", root_dir=str(git.root))
        generate.assert_called_once_with(git, pathlib.Path("/clone/news"))
        commit.assert_called_once_with(git, news_file, False)

    @mock.patch("continuous_delivery_scripts.assert_news.generate_news_file")
    @mock.patch("continuous_delivery_scripts.assert_news.ProjectTempClone")
    @mock.patch("continuous_delivery_scripts.assert_news.configuration.get_value")
    def test_dependabot_news_file_on_branch_is_validated_in_clone(self, get_value, temp_clone, generate_news_file):
        with TemporaryDirectory() as clone_root:
            news_path = pathlib.Path(clone_root, "news", "123.bugfix")
            news_path.parent.mkdir()
            news_path.write_text("Dependency upgrade: example\n")
            git = mock.Mock(spec_set=GitWrapper)
            git.root = pathlib.Path(clone_root)
            git.is_current_branch_feature.return_value = True
            git.list_files_added_to_current_commit.return_value = []
            git.list_files_added_on_current_branch.return_value = ["news/123.bugfix"]
            temp_clone.return_value.__enter__.return_value = git
            project_root = pathlib.Path(clone_root, "original-project")
            get_value.side_effect = {
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.NEWS_DIR: str(project_root / "news"),
            }.get

            with mock.patch("sys.argv", ["cd-assert-news", "-b", "dependabot/pip/example"]):
                main()

            git.list_files_added_on_current_branch.assert_called_once_with()
            generate_news_file.assert_not_called()

    @mock.patch("continuous_delivery_scripts.assert_news.generate_news_file")
    @mock.patch("continuous_delivery_scripts.assert_news.ProjectTempClone")
    @mock.patch("continuous_delivery_scripts.assert_news.configuration.get_value")
    def test_invalid_existing_news_file_does_not_generate_another(self, get_value, temp_clone, generate_news_file):
        with TemporaryDirectory() as clone_root:
            news_path = pathlib.Path(clone_root, "news", "123.bugfix")
            news_path.parent.mkdir()
            news_path.write_text("Two\nlines\n")
            git = mock.Mock(spec_set=GitWrapper)
            git.root = pathlib.Path(clone_root)
            git.is_current_branch_feature.return_value = True
            git.list_files_added_to_current_commit.return_value = []
            git.list_files_added_on_current_branch.return_value = ["news/123.bugfix"]
            temp_clone.return_value.__enter__.return_value = git
            project_root = pathlib.Path(clone_root, "original-project")
            get_value.side_effect = {
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.NEWS_DIR: str(project_root / "news"),
            }.get

            with mock.patch("sys.argv", ["cd-assert-news", "-b", "dependabot/pip/example"]):
                with self.assertRaises(SystemExit) as cm:
                    main()

            self.assertEqual(cm.exception.code, 1)
            generate_news_file.assert_not_called()

    @mock.patch("continuous_delivery_scripts.assert_news.generate_news_file")
    @mock.patch("continuous_delivery_scripts.assert_news.ProjectTempClone")
    @mock.patch("continuous_delivery_scripts.assert_news.configuration.get_value")
    def test_unreadable_existing_news_file_does_not_generate_another(self, get_value, temp_clone, generate_news_file):
        with TemporaryDirectory() as clone_root:
            git = mock.Mock(spec_set=GitWrapper)
            git.root = pathlib.Path(clone_root)
            git.is_current_branch_feature.return_value = True
            git.list_files_added_to_current_commit.return_value = []
            git.list_files_added_on_current_branch.return_value = ["news/123.bugfix"]
            temp_clone.return_value.__enter__.return_value = git
            project_root = pathlib.Path(clone_root, "original-project")
            get_value.side_effect = {
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.NEWS_DIR: str(project_root / "news"),
            }.get

            with mock.patch("sys.argv", ["cd-assert-news", "-b", "dependabot/pip/example"]):
                with self.assertRaises(SystemExit) as cm:
                    main()

            self.assertEqual(cm.exception.code, 1)
            generate_news_file.assert_not_called()
