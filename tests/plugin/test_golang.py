#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import shutil
from pathlib import Path
from unittest import TestCase, mock
from unittest import skipUnless

from continuous_delivery_scripts.plugins import golang
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory

GO_AVAILABLE = shutil.which("go") is not None


class TestGoModuleTags(TestCase):
    def test_determine_go_module_tag_keeps_current_module(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(golang, "SRC_DIR", source_dir):
                tags = golang._determine_go_module_tag("v1.2.3")

            self.assertEqual(tags, ["src/v1.2.3"])

    def test_determine_go_module_tag_reads_go_work_modules(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()
            root.joinpath("go.work").touch()

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(
                golang, "SRC_DIR", source_dir
            ), mock.patch.object(
                golang,
                "check_output",
                return_value='{"Use": [{"DiskPath": "./app1"}, {"DiskPath": "./nested/app2"}]}',
            ):
                tags = golang._determine_go_module_tag("v1.2.3")

            self.assertEqual(tags, ["src/v1.2.3", "app1/v1.2.3", "nested/app2/v1.2.3"])

    def test_determine_go_module_tag_reads_go_work_from_source_dir(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()
            source_dir.joinpath("go.work").touch()

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(
                golang, "SRC_DIR", source_dir
            ), mock.patch.object(
                golang,
                "check_output",
                return_value='{"Use": [{"DiskPath": "./app1"}, {"DiskPath": "./nested/app2"}]}',
            ):
                tags = golang._determine_go_module_tag("v1.2.3")

            self.assertEqual(tags, ["src/v1.2.3", "src/app1/v1.2.3", "src/nested/app2/v1.2.3"])

    def test_determine_go_module_tag_reads_multiple_go_work_files(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()
            root.joinpath("go.work").touch()
            source_dir.joinpath("go.work").touch()

            def check_output_side_effect(command, cwd=None, encoding=None):
                if Path(str(cwd)) == source_dir:
                    return '{"Use": [{"DiskPath": "./app1"}]}'
                if Path(str(cwd)) == root:
                    return '{"Use": [{"DiskPath": "./shared"}, {"DiskPath": "./root-app"}]}'
                raise AssertionError(f"Unexpected cwd: {cwd}")

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(
                golang, "SRC_DIR", source_dir
            ), mock.patch.object(golang, "check_output", side_effect=check_output_side_effect):
                tags = golang._determine_go_module_tag("v1.2.3")

            self.assertEqual(tags, ["src/v1.2.3", "src/app1/v1.2.3", "shared/v1.2.3", "root-app/v1.2.3"])

    def test_determine_go_module_tag_reads_nested_go_mod_projects(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()
            source_dir.joinpath("go.mod").write_text("module example.com/src\n", encoding="utf8")
            source_dir.joinpath("service-a").mkdir()
            source_dir.joinpath("service-a", "go.mod").write_text("module example.com/service-a\n", encoding="utf8")
            source_dir.joinpath("service-b").mkdir()
            source_dir.joinpath("service-b", "go.mod").write_text("module example.com/service-b\n", encoding="utf8")

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(golang, "SRC_DIR", source_dir):
                tags = golang._determine_go_module_tag("v1.2.3")

            self.assertEqual(tags, ["src/v1.2.3", "src/service-a/v1.2.3", "src/service-b/v1.2.3"])


@skipUnless(GO_AVAILABLE, "go command is required for this integration test")
class TestGoWorkIntegration(TestCase):
    def test_determine_go_work_module_directories_from_json_with_go(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            root.joinpath("go.work").write_text("go 1.22\n\nuse ./app1\n", encoding="utf8")
            root.joinpath("app1").mkdir()

            directories = golang._determine_go_work_module_directories_from_json(root.joinpath("go.work"))

            self.assertEqual(directories, [root.joinpath("app1")])
