#!/usr/bin/env python
#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest import TestCase, mock, skipUnless

from continuous_delivery_scripts.generate_news import _generate_changelog, _normalise_markdown_release_headings
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration


class TestGenerateNews(TestCase):
    @mock.patch("continuous_delivery_scripts.generate_news._normalise_markdown_release_headings")
    @mock.patch("continuous_delivery_scripts.generate_news.subprocess.check_call")
    def test_generate_changelog_invokes_towncrier_with_separate_option_values(self, check_call, normalise):
        with TemporaryDirectory() as temp_dir:
            project_config = Path(temp_dir) / "pyproject.toml"
            project_config.write_text("[tool.towncrier]\n", encoding="utf8")
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

        self.assertIn("1.2.3", rendered)
        self.assertIn("Bugfixes", rendered)
        self.assertIn("Fixed example bug.", rendered)

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
                _normalise_markdown_release_headings("1.2.3")

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
                _normalise_markdown_release_headings("1.2.3")

            rendered = changelog.read_text(encoding="utf8")

        self.assertEqual(rendered, original)
