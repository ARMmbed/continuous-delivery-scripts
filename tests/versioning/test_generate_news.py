#!/usr/bin/env python
#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest import TestCase, mock, skipUnless

import toml

from continuous_delivery_scripts.generate_news import _generate_changelog
from continuous_delivery_scripts.utils.changelog import normalise_markdown_release_headings
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration


class TestGenerateNews(TestCase):
    @mock.patch("continuous_delivery_scripts.generate_news.generate_changelog")
    def test_generate_changelog_invokes_changelog_utility(self, generate):
        _generate_changelog("1.2.3", True)

        generate.assert_called_once_with("1.2.3")

    @mock.patch("continuous_delivery_scripts.utils.changelog.normalise_markdown_release_headings")
    @mock.patch("continuous_delivery_scripts.utils.changelog.subprocess.check_call")
    def test_generate_changelog_does_not_duplicate_existing_markdown_heading(self, check_call, normalise):
        with TemporaryDirectory() as temp_dir:
            project_config = Path(temp_dir) / "pyproject.toml"
            project_config.write_text(
                "[tool.towncrier]\n" 'title_format = "# {version} ({project_date})"\n', encoding="utf8"
            )
            get_value = configuration.get_value

            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    str(project_config) if key == ConfigurationVariable.PROJECT_CONFIG else get_value(key)
                ),
            ):
                _generate_changelog("1.2.3", True)

        check_call.assert_called_once_with(["towncrier", "build", "--yes", "--name", "", "--version", "1.2.3"])
        normalise.assert_called_once_with("1.2.3")

    @mock.patch("continuous_delivery_scripts.utils.changelog.normalise_markdown_release_headings")
    @mock.patch("continuous_delivery_scripts.utils.changelog.subprocess.check_call")
    def test_generate_changelog_adds_markdown_heading_workaround_when_missing(self, check_call, normalise):
        with TemporaryDirectory() as temp_dir:
            project_config = Path(temp_dir) / "pyproject.toml"
            project_config.write_text(
                "[tool.towncrier]\n" 'title_format = "{version} ({project_date})"\n', encoding="utf8"
            )
            get_value = configuration.get_value
            temp_config_path = None

            def inspect_call(command):
                nonlocal temp_config_path
                temp_config_path = Path(command[command.index("--config") + 1])
                config = toml.load(temp_config_path)
                self.assertEqual(config["tool"]["towncrier"]["title_format"], "# {version} ({project_date})")

            check_call.side_effect = inspect_call

            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    str(project_config) if key == ConfigurationVariable.PROJECT_CONFIG else get_value(key)
                ),
            ):
                _generate_changelog("1.2.3", True)

        self.assertIsNotNone(temp_config_path)
        self.assertFalse(temp_config_path.exists())
        normalise.assert_called_once_with("1.2.3")

    @skipUnless(which("towncrier"), "towncrier executable required")
    def test_generate_changelog_builds_release_notes_with_towncrier(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_config = root / "pyproject.toml"
            changelog = root / "CHANGELOG.md"
            news_dir = root / "news"
            news_dir.mkdir()
            (news_dir / "123.bugfix").write_text("Fixed example bug.\n", encoding="utf8")
            changelog.write_text("# Changelog\n\n[//]: # (begin_release_notes)\n", encoding="utf8")
            project_config.write_text(
                "[tool.towncrier]\n"
                'directory = "news"\n'
                'filename = "CHANGELOG.md"\n'
                'package = "continuous_delivery_scripts"\n'
                'title_format = "{version} ({project_date})"\n'
                'start_string = """\n'
                "[//]: # (begin_release_notes)\n"
                '"""\n\n'
                "[[tool.towncrier.type]]\n"
                'directory = "bugfix"\n'
                'name = "Bugfixes"\n'
                "showcontent = true\n",
                encoding="utf8",
            )
            get_value = configuration.get_value

            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    str(project_config) if key == ConfigurationVariable.PROJECT_CONFIG else get_value(key)
                ),
            ):
                _generate_changelog("1.2.3", True)

            rendered = changelog.read_text(encoding="utf8")

        self.assertIn("# 1.2.3", rendered)
        self.assertIn("Bugfixes", rendered)
        self.assertIn("Fixed example bug.", rendered)

    def test_generate_changelog_does_nothing_when_news_files_are_disabled(self):
        with mock.patch("continuous_delivery_scripts.generate_news.generate_changelog") as generate:
            _generate_changelog("1.2.3", False)

        generate.assert_not_called()

    def test_normalise_markdown_release_headings_promotes_latest_release_title(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            changelog.write_text(
                "# Changelog\n\n"
                "[//]: # (begin_release_notes)\n\n"
                "1.2.3 (2026-10-02)\n\n"
                "# Bugfixes\n\n"
                "- Fixed example bug. (#123)\n\n"
                '"1.2.2" (2026-10-01)\n'
                "====================\n\n"
                "Bugfixes\n"
                "--------\n",
                encoding="utf8",
            )
            get_value = configuration.get_value

            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    str(changelog) if key == ConfigurationVariable.CHANGELOG_FILE_PATH else get_value(key)
                ),
            ):
                normalise_markdown_release_headings("1.2.3")

            rendered = changelog.read_text(encoding="utf8")

        self.assertIn("# 1.2.3 (2026-10-02)", rendered)
        self.assertIn("## Bugfixes", rendered)
        self.assertIn('"1.2.2" (2026-10-01)', rendered)

    def test_normalise_markdown_release_headings_leaves_existing_heading_alone(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            original = (
                "# Changelog\n\n"
                "[//]: # (begin_release_notes)\n\n"
                "# 1.2.3 (2026-10-02)\n\n"
                "## Bugfixes\n\n"
                "- Fixed example bug. (#123)\n"
            )
            changelog.write_text(original, encoding="utf8")
            get_value = configuration.get_value

            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    str(changelog) if key == ConfigurationVariable.CHANGELOG_FILE_PATH else get_value(key)
                ),
            ):
                normalise_markdown_release_headings("1.2.3")

            rendered = changelog.read_text(encoding="utf8")

        self.assertEqual(rendered, original)
