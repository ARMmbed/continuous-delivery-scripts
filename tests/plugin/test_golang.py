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

            def check_output_side_effect(command, encoding=None, stderr=None):
                if Path(command[-1]) == source_dir / "go.work":
                    return '{"Use": [{"DiskPath": "./app1"}]}'
                if Path(command[-1]) == root / "go.work":
                    return '{"Use": [{"DiskPath": "./shared"}, {"DiskPath": "./root-app"}]}'
                raise AssertionError(f"Unexpected workspace: {command[-1]}")

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

    def test_workspace_tag_discovery_uses_shared_metadata_reader(self):
        workspace = Path("project/go.work")
        with mock.patch.object(
            golang, "_read_go_workspace_metadata", return_value={"Use": [{"DiskPath": "./app1"}]}
        ) as read_metadata:
            directories = golang._determine_go_work_module_directories_from_json(workspace)
        self.assertEqual(directories, [workspace.parent / "app1"])
        read_metadata.assert_called_once_with(workspace)

    def test_doc2go_discovers_actual_go_work_modules(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            root.joinpath("go.work").write_text("go 1.22\n\nuse (\n ./generator\n ./cli\n)\n", encoding="utf8")
            for name in ("generator", "cli"):
                module = root / name
                module.mkdir()
                (module / "go.mod").write_text(f"module example.com/{name}\n\ngo 1.22\n", encoding="utf8")

            with mock.patch.object(golang, "SRC_DIR", root), mock.patch.object(golang, "ROOT_DIR", root):
                self.assertEqual(golang._doc2go_target("."), (root, ["./generator/...", "./cli/..."]))
                self.assertEqual(golang._doc2go_target("cli"), (root / "cli", ["./..."]))


class TestGoDocumentation(TestCase):
    def test_doc2go_selects_configured_module(self):
        with TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "generator"
            source_dir.mkdir()
            (source_dir / "go.mod").write_text("module example.com/generator\n", encoding="utf8")
            (source_dir / "config").mkdir()

            with mock.patch.object(golang, "SRC_DIR", source_dir), mock.patch.object(
                golang, "ROOT_DIR", Path(temp_dir)
            ):
                self.assertEqual(golang._doc2go_target("generator"), (source_dir, ["./..."]))
                self.assertEqual(golang._doc2go_target("config"), (source_dir, ["./config/..."]))
                self.assertEqual(golang._doc2go_target("generator/config"), (source_dir, ["./config/..."]))
                with mock.patch.object(golang, "_go_module_name", return_value="example.com/generator"):
                    self.assertEqual(golang._doc2go_target("example.com/generator"), (source_dir, ["./..."]))
                    self.assertEqual(
                        golang._doc2go_target("example.com/generator/api"),
                        (source_dir, ["example.com/generator/api"]),
                    )

    def test_doc2go_discovers_workspace_modules_and_selects_one(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            modules = [root / "generator", root / "cli"]
            for module in modules:
                module.mkdir()
                (module / "go.mod").write_text(f"module example.com/{module.name}\n", encoding="utf8")
            (root / "go.work").touch()

            with mock.patch.object(golang, "SRC_DIR", root), mock.patch.object(
                golang, "ROOT_DIR", root
            ), mock.patch.object(golang, "_determine_go_work_module_directories", return_value=modules):
                self.assertEqual(golang._doc2go_target("."), (root, ["./generator/...", "./cli/..."]))
                self.assertEqual(golang._doc2go_target("cli"), (root / "cli", ["./..."]))
                self.assertEqual(golang._doc2go_target("./generator"), (root / "generator", ["./..."]))

            with mock.patch.object(golang, "SRC_DIR", root / "generator"), mock.patch.object(
                golang, "ROOT_DIR", root
            ), mock.patch.object(golang, "_determine_go_work_module_directories", return_value=modules):
                self.assertEqual(golang._doc2go_target("cli"), (root / "cli", ["./..."]))

    def test_doc2go_discovers_module_above_source_directory(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "go.mod").write_text("module example.com/project\n", encoding="utf8")
            source_dir = root / "src"
            source_dir.mkdir()

            with mock.patch.object(golang, "SRC_DIR", source_dir), mock.patch.object(golang, "ROOT_DIR", root):
                self.assertEqual(golang._doc2go_target("src"), (root, ["./src/..."]))

    def test_doc2go_requires_a_documentation_target(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(golang, "SRC_DIR", root), mock.patch.object(golang, "ROOT_DIR", root):
                with self.assertRaisesRegex(ValueError, "MODULE_TO_DOCUMENT"):
                    golang._doc2go_target("")

    def test_doc2go_rejects_ambiguous_package_names(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "go.mod").write_text("module example.com/root\n", encoding="utf8")
            (root / "config").mkdir()
            source = root / "generator"
            source.mkdir()
            (source / "go.mod").write_text("module example.com/generator\n", encoding="utf8")
            (source / "config").mkdir()

            with mock.patch.object(golang, "SRC_DIR", source), mock.patch.object(golang, "ROOT_DIR", root):
                with self.assertRaisesRegex(ValueError, "several Go packages"):
                    golang._doc2go_target("config")
                self.assertEqual(golang._doc2go_target("generator/config"), (source, ["./config/..."]))

    @mock.patch.object(golang, "check_call")
    @mock.patch.object(golang, "_ensure_go_tool_installed", return_value="C:/go/bin/doc2go")
    def test_call_doc2go_uses_resolved_executable_and_source_dir(self, ensure_installed, check_call):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root.joinpath("src")
            source_dir.mkdir()
            output_dir = root.joinpath("docs")

            with mock.patch.object(golang, "SRC_DIR", source_dir):
                golang._call_doc2go(output_dir, "example.com/module")

        ensure_installed.assert_called_once()
        check_call.assert_called_once_with(
            ["C:/go/bin/doc2go", "-out", str(output_dir), "example.com/module"],
            cwd=str(source_dir),
            env=mock.ANY,
        )

    @mock.patch.object(golang, "check_call")
    @mock.patch.object(golang, "_ensure_go_tool_installed", return_value="doc2go")
    def test_call_doc2go_uses_configured_workspace_patterns(self, _ensure_installed, check_call):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(golang, "SRC_DIR", root), mock.patch.object(
                golang, "_doc2go_target", return_value=(root, ["./generator/...", "./cli/..."])
            ):
                golang._call_doc2go(root / "docs", ".")

        check_call.assert_called_once_with(
            ["doc2go", "-out", str(root / "docs"), "./generator/...", "./cli/..."],
            cwd=str(root),
            env=mock.ANY,
        )

    @mock.patch.object(golang, "check_call")
    @mock.patch.object(golang, "_ensure_go_tool_installed", return_value="doc2go")
    def test_call_doc2go_keeps_relative_output_under_callers_directory(self, _ensure_installed, check_call):
        with TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "generator"
            source_dir.mkdir()
            (source_dir / "go.mod").write_text("module example.com/generator\n", encoding="utf8")

            with mock.patch.object(golang, "SRC_DIR", source_dir), mock.patch.object(
                golang, "ROOT_DIR", Path(temp_dir)
            ):
                golang._call_doc2go(Path("docs"), "generator")

        check_call.assert_called_once_with(
            ["doc2go", "-out", str(Path("docs").resolve()), "./..."],
            cwd=str(source_dir),
            env=mock.ANY,
        )

    @mock.patch.object(golang, "_call_doc2go")
    def test_go_plugin_delegates_documentation_generation_to_doc2go(self, call_doc2go):
        output_dir = Path("docs")

        golang.Go().generate_code_documentation(output_dir, "example.com/module")

        call_doc2go.assert_called_once_with(output_dir, "example.com/module")
