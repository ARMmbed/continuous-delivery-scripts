#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from unittest import TestCase, mock

from continuous_delivery_scripts.tag_and_release import tag_and_release
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, StaticConfig, configuration
from continuous_delivery_scripts.utils.definitions import CommitType


class TestReleaseLicensingSummary(TestCase):
    def test_default_is_to_skip_release_summary(self):
        self.assertFalse(StaticConfig().get_value(ConfigurationVariable.GENERATE_LICENSING_SUMMARY_ON_RELEASE))

    def test_this_project_enables_release_summary(self):
        self.assertTrue(configuration.get_value(ConfigurationVariable.GENERATE_LICENSING_SUMMARY_ON_RELEASE))

    def test_release_skips_summary_when_disabled(self):
        for configured_value in (False, "false"):
            with self.subTest(configured_value=configured_value):
                with (
                    mock.patch(
                        "continuous_delivery_scripts.tag_and_release.configuration.get_value",
                        return_value=configured_value,
                    ),
                    mock.patch("continuous_delivery_scripts.tag_and_release.get_language_specifics"),
                    mock.patch(
                        "continuous_delivery_scripts.tag_and_release.version_project", return_value=(False, "1.2.3", {})
                    ),
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_documentation") as update_docs,
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_licensing_summary") as summary,
                    mock.patch("continuous_delivery_scripts.tag_and_release.insert_licence_header"),
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_repository") as update_repository,
                ):
                    tag_and_release(CommitType.BETA)

                update_docs.assert_called_once_with()
                summary.assert_not_called()
                update_repository.assert_called_once()

    def test_release_generates_summary_when_enabled(self):
        for configured_value in (True, "true"):
            with self.subTest(configured_value=configured_value):
                with (
                    mock.patch(
                        "continuous_delivery_scripts.tag_and_release.configuration.get_value",
                        return_value=configured_value,
                    ),
                    mock.patch("continuous_delivery_scripts.tag_and_release.get_language_specifics"),
                    mock.patch(
                        "continuous_delivery_scripts.tag_and_release.version_project", return_value=(False, "1.2.3", {})
                    ),
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_documentation") as update_docs,
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_licensing_summary") as summary,
                    mock.patch("continuous_delivery_scripts.tag_and_release.insert_licence_header"),
                    mock.patch("continuous_delivery_scripts.tag_and_release._update_repository"),
                ):
                    tag_and_release(CommitType.BETA)

                update_docs.assert_called_once_with()
                summary.assert_called_once_with()

    def test_explicit_package_spdx_generation_does_not_require_release_summary(self):
        spdx_project = mock.Mock()
        with (
            mock.patch("continuous_delivery_scripts.tag_and_release.configuration.get_value", return_value=False),
            mock.patch("continuous_delivery_scripts.tag_and_release.get_language_specifics") as language_plugin,
            mock.patch("continuous_delivery_scripts.tag_and_release.version_project", return_value=(True, "1.2.3", {})),
            mock.patch("continuous_delivery_scripts.tag_and_release._update_documentation"),
            mock.patch("continuous_delivery_scripts.tag_and_release._update_licensing_summary") as summary,
            mock.patch("continuous_delivery_scripts.tag_and_release.insert_licence_header"),
            mock.patch("continuous_delivery_scripts.tag_and_release._update_repository"),
            mock.patch("continuous_delivery_scripts.tag_and_release._generate_spdx_reports") as generate_reports,
        ):
            language_plugin.return_value.should_include_spdx_in_package.return_value = True
            language_plugin.return_value.can_get_project_metadata.return_value = True
            language_plugin.return_value.should_clean_before_packaging.return_value = False
            language_plugin.return_value.get_current_spdx_project.return_value = spdx_project

            tag_and_release(CommitType.RELEASE)

        summary.assert_not_called()
        generate_reports.assert_called_once_with(spdx_project)
