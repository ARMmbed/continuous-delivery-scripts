#!/usr/bin/env python
#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from unittest import TestCase, mock, skipUnless

from continuous_delivery_scripts.generate_news import _generate_changelog
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration


class TestGenerateNews(TestCase):
    @mock.patch("continuous_delivery_scripts.generate_news.generate_changelog")
    def test_generate_changelog_invokes_changelog_utility(self, generate):
        _generate_changelog("1.2.3", True)

        generate.assert_called_once_with("1.2.3")

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
