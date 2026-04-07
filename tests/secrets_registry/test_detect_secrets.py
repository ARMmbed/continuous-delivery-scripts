#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from pathlib import Path
from unittest import TestCase, mock

from continuous_delivery_scripts.detect_secrets import (
    _filter_tracked_files,
    _generate_detect_secrets_hook_command_list,
    detect_secrets,
)


class TestDetectSecrets(TestCase):
    def test_filter_tracked_files_excludes_registry(self):
        filtered_files = _filter_tracked_files(
            ["foo.py", ".secrets.baseline", "bar.txt"],
            Path("/repo"),
            Path("/repo/.secrets.baseline"),
        )

        self.assertEqual(filtered_files, ["foo.py", "bar.txt"])

    def test_generate_detect_secrets_hook_command_list(self):
        command = _generate_detect_secrets_hook_command_list(
            Path(".secrets.baseline"), [r".*\.html$"], ["foo.py", "bar.txt"]
        )

        self.assertEqual(
            command,
            [
                "detect-secrets-hook",
                "--baseline",
                ".secrets.baseline",
                "--exclude-files",
                r".*\.html$",
                "foo.py",
                "bar.txt",
            ],
        )

    @mock.patch("continuous_delivery_scripts.detect_secrets.subprocess.check_call")
    @mock.patch("continuous_delivery_scripts.detect_secrets._determine_exclude_files")
    @mock.patch("continuous_delivery_scripts.detect_secrets.ProjectGitWrapper")
    @mock.patch("continuous_delivery_scripts.detect_secrets._get_secrets_baseline_file")
    def test_detect_secrets_runs_on_git_tracked_files(
        self, get_baseline_file, ProjectGitWrapper, determine_exclude_files, check_call
    ):
        project_root = Path("/repo")
        get_baseline_file.return_value = project_root.joinpath(".secrets.baseline")
        determine_exclude_files.return_value = [r".*\.html$"]
        ProjectGitWrapper.return_value.root = project_root
        ProjectGitWrapper.return_value.list_tracked_files.return_value = [
            "foo.py",
            "bar.txt",
            ".secrets.baseline",
        ]

        detect_secrets()

        check_call.assert_called_once_with(
            [
                "detect-secrets-hook",
                "--baseline",
                str(project_root.joinpath(".secrets.baseline")),
                "--exclude-files",
                r".*\.html$",
                "foo.py",
                "bar.txt",
            ],
            cwd=str(project_root),
        )

    @mock.patch("continuous_delivery_scripts.detect_secrets.subprocess.check_call")
    @mock.patch("continuous_delivery_scripts.detect_secrets._determine_exclude_files")
    @mock.patch("continuous_delivery_scripts.detect_secrets.ProjectGitWrapper")
    @mock.patch("continuous_delivery_scripts.detect_secrets._get_secrets_baseline_file")
    def test_detect_secrets_skips_when_no_tracked_files(
        self, get_baseline_file, ProjectGitWrapper, determine_exclude_files, check_call
    ):
        project_root = Path("/repo")
        get_baseline_file.return_value = project_root.joinpath(".secrets.baseline")
        determine_exclude_files.return_value = [r".*\.html$"]
        ProjectGitWrapper.return_value.root = project_root
        ProjectGitWrapper.return_value.list_tracked_files.return_value = []

        detect_secrets()

        check_call.assert_not_called()
