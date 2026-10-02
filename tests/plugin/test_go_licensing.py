#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock, skipUnless

from continuous_delivery_scripts.plugins import golang
from continuous_delivery_scripts.spdx_report.spdx_package import PackageInfo, SpdxPackage
from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.package_helpers import LicenceSource, PackageMetadata, ProjectMetadata
from spdx_tools.spdx.parser.parse_anything import parse_file
from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document


class TestGoLicenceCollection(TestCase):
    def test_install_command_uses_v2_module(self):
        self.assertEqual(
            golang._install_go_licenses_command_list(), ["go", "install", "github.com/google/go-licenses/v2@latest"]
        )

    @mock.patch.object(golang, "check_call")
    @mock.patch.object(golang, "check_output", return_value=b"go-licenses help")
    @mock.patch.object(golang.shutil, "which", return_value="/tools/go-licenses")
    def test_reuses_go_licenses_already_on_path(self, which, check_output, check_call):
        env = {"GO111MODULE": "on"}

        executable = golang._ensure_go_tool_installed(
            "go-licenses", ["go-licenses", "report", "--help"], golang._install_go_licenses_command_list(), env
        )

        self.assertEqual(executable, "/tools/go-licenses")
        which.assert_called_once_with("go-licenses")
        check_output.assert_any_call(["go-licenses", "report", "--help"], env=env)
        check_call.assert_not_called()

    @mock.patch.object(golang, "_installed_go_tool_path", return_value="/go/bin/go-licenses")
    @mock.patch.object(golang, "check_call")
    @mock.patch.object(golang.shutil, "which", return_value=None)
    def test_installs_go_licenses_when_missing(self, _which, check_call, installed_path):
        env = {"GO111MODULE": "on"}

        executable = golang._ensure_go_tool_installed(
            "go-licenses", ["go-licenses", "report", "--help"], golang._install_go_licenses_command_list(), env
        )

        self.assertEqual(executable, "/go/bin/go-licenses")
        check_call.assert_called_once_with(["go", "install", "github.com/google/go-licenses/v2@latest"], env=env)
        installed_path.assert_called_once_with("go-licenses", env)

    @mock.patch.object(golang, "check_output")
    def test_uses_go_binary_directory_after_installation(self, check_output):
        with TemporaryDirectory() as temp_dir:
            binary = Path(temp_dir, "go-licenses.exe" if os.name == "nt" else "go-licenses")
            binary.touch()
            check_output.return_value = str(binary.parent)

            self.assertEqual(golang._installed_go_tool_path("go-licenses", {}), str(binary))

        check_output.assert_called_once_with(["go", "env", "GOBIN"], env={}, encoding="utf8")

    @mock.patch.object(golang, "check_output")
    def test_uses_gopath_when_gobin_is_not_set(self, check_output):
        with TemporaryDirectory() as temp_dir:
            go_bin = Path(temp_dir, "bin")
            go_bin.mkdir()
            binary = go_bin / ("go-licenses.exe" if os.name == "nt" else "go-licenses")
            binary.touch()
            check_output.side_effect = ["", temp_dir]

            self.assertEqual(golang._installed_go_tool_path("go-licenses", {}), str(binary))

        self.assertEqual(check_output.call_count, 2)

    def test_reports_missing_module_before_installing_tools(self):
        with TemporaryDirectory() as temp_dir, mock.patch.object(
            golang, "SRC_DIR", Path(temp_dir, "source")
        ), mock.patch.object(golang, "ROOT_DIR", Path(temp_dir)), mock.patch.object(
            golang, "_ensure_go_tool_installed"
        ) as ensure_installed:
            with self.assertRaisesRegex(FileNotFoundError, "go.mod"):
                golang.GoProjectMetadataFetcher().project_metadata

        ensure_installed.assert_not_called()

    @mock.patch.object(golang, "_determine_go_work_module_directories")
    def test_reports_workspace_modules(self, workspace_modules):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            modules = [root / "app", root / "tool"]
            for module in modules:
                module.mkdir()
                (module / "go.mod").write_text(f"module example.com/{module.name}\n", encoding="utf8")
            workspace_modules.return_value = modules

            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(golang, "SRC_DIR", root):
                self.assertEqual(golang._go_licence_module_directories(), modules)

    @mock.patch.object(golang, "check_output", return_value='{"Path": "example.com/acme"}')
    def test_go_module_name_disables_go_work_to_scope_metadata_to_one_module(self, check_output):
        env = {"GO111MODULE": "on", "GOWORK": "auto"}

        name = golang._go_module_name(Path("module"), env)

        self.assertEqual(name, "example.com/acme")
        check_output.assert_called_once_with(
            ["go", "list", "-m", "-json"],
            cwd=Path("module"),
            env={"GO111MODULE": "on", "GOWORK": "off"},
            encoding="utf8",
        )

    def test_parses_licences_and_keeps_unknown_for_shared_policy(self):
        packages = golang._parse_go_licences(
            "github.com/acme/dep\tv1.2.3\thttps://github.com/acme/dep/blob/v1.2.3/LICENSE\tMIT\n"
            "github.com/acme/unknown\tv0.1.0\tUnknown\tUnknown\n"
        )

        self.assertEqual(packages[0].name, "github.com/acme/dep")
        self.assertEqual(packages[0].version, "v1.2.3")
        self.assertEqual(packages[0].licence, "MIT")
        self.assertEqual(packages[0].licence_source, "tool")
        self.assertEqual(packages[0].licence_evidence[0]["kind"], "licence")
        self.assertEqual(packages[1].licence_source, "unknown")
        self.assertTrue(packages[1].has_unknown_licence)
        with self.assertRaisesRegex(ValueError, "Unexpected go-licenses report row"):
            golang._parse_go_licences("missing\tcolumns\n")

    @mock.patch.object(golang.logger, "info")
    @mock.patch.object(golang.logger, "warning")
    def test_logs_go_licenses_stderr_through_cds_logging(self, warning, info):
        golang._log_go_licenses_stderr(Path("module"), "warning one\nwarning two\n")

        warning.assert_called_once()
        info.assert_called_once_with("go-licenses stderr for [%s]:\n%s", Path("module"), "warning one\nwarning two")

    @mock.patch.object(golang, "run")
    def test_run_go_licenses_report_captures_stderr_and_returns_stdout(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["go-licenses"], returncode=0, stdout="package\tversion\turl\tlicence\n", stderr="stderr line\n"
        )
        with mock.patch.object(golang, "_log_go_licenses_stderr") as log_stderr:
            output = golang._run_go_licenses_report(
                "go-licenses", Path("module"), Path("template"), {"GO111MODULE": "on"}
            )

        self.assertEqual(output, "package\tversion\turl\tlicence\n")
        log_stderr.assert_called_once_with(Path("module"), "stderr line\n")

    @mock.patch.object(golang, "run")
    def test_run_go_licenses_report_raises_with_captured_output_on_failure(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["go-licenses"], returncode=1, stdout="", stderr="fatal stderr\n"
        )

        with self.assertRaises(subprocess.CalledProcessError) as error:
            golang._run_go_licenses_report("go-licenses", Path("module"), Path("template"), {})

        self.assertEqual(error.exception.stderr, "fatal stderr")

    def test_stages_root_licence_for_modules_without_one_and_cleans_up(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            module_without_licence = root / "service-a"
            module_without_licence.mkdir()
            module_with_licence = root / "service-b"
            module_with_licence.mkdir()
            root_licence = root / "LICENSE"
            root_licence.write_text("root licence", encoding="utf8")
            existing_licence = module_with_licence / "LICENSE"
            existing_licence.write_text("module licence", encoding="utf8")

            with mock.patch.object(golang, "ROOT_DIR", root):
                with golang._stage_root_licence_files_for_modules([module_without_licence, module_with_licence]):
                    self.assertEqual((module_without_licence / "LICENSE").read_text(encoding="utf8"), "root licence")
                    self.assertEqual(existing_licence.read_text(encoding="utf8"), "module licence")

            self.assertFalse((module_without_licence / "LICENSE").exists())
            self.assertEqual(existing_licence.read_text(encoding="utf8"), "module licence")

    @mock.patch.object(golang, "_go_licence_module_directories")
    @mock.patch.object(golang, "_ensure_go_tool_installed", return_value="go-licenses")
    @mock.patch.object(golang, "check_output")
    @mock.patch.object(golang, "run")
    def test_go_project_uses_shared_metadata(self, run_mock, check_output, ensure_installed, module_directories):
        with TemporaryDirectory() as temp_dir:
            module_directories.return_value = [Path(temp_dir)]

            def output(command, **kwargs):
                if command[:4] == ["go", "list", "-m", "-json"]:
                    return '{"Path": "example.com/acme"}'

            check_output.side_effect = output

            def run_side_effect(command, **kwargs):
                template_path = Path(command[-1])
                self.assertIn("{{.Version}}", template_path.read_text(encoding="utf8"))
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=(
                        "example.com/acme\t\tUnknown\tApache-2.0\n"
                        "example.com/acme/internal/tool\t\tUnknown\tApache-2.0\n"
                        "github.com/acme/dep\tv1.2.3\thttps://example.com/LICENSE\tMIT\n"
                        "github.com/acme/ambiguous\tv1.0.0\thttps://example.com/MIT\tMIT\n"
                        "github.com/acme/ambiguous\tv1.0.0\thttps://example.com/BSD\tBSD-3-Clause\n"
                        "github.com/acme/ambiguous\tv1.0.0\thttps://example.com/Apache\tApache-2.0\n"
                    ),
                    stderr="",
                )

            run_mock.side_effect = run_side_effect
            get_value = configuration.get_value
            with mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    "Acme"
                    if key == ConfigurationVariable.PROJECT_NAME
                    else "Apache-2.0" if key == ConfigurationVariable.FILE_LICENCE_IDENTIFIER else get_value(key)
                ),
            ):
                project = golang.GoProjectMetadataFetcher().project_metadata

        self.assertEqual(project.project_metadata.name, "Acme")
        self.assertEqual(project.project_metadata.licence, "Apache-2.0")
        self.assertEqual(project.project_metadata.licence_source, "configuration")
        self.assertEqual(
            [package.name for package in project.dependencies_metadata],
            ["github.com/acme/dep", "github.com/acme/ambiguous"],
        )
        self.assertEqual(project.dependencies_metadata[0].licence, "MIT")
        self.assertEqual(project.dependencies_metadata[1].licence_source, "unknown")
        self.assertEqual(project.dependencies_metadata[1].licence_candidates, ["Apache-2.0", "BSD-3-Clause", "MIT"])
        ensure_installed.assert_called_once()

    @mock.patch.object(golang, "_go_licence_module_directories")
    @mock.patch.object(golang, "_ensure_go_tool_installed", return_value="go-licenses")
    @mock.patch.object(golang, "check_output")
    @mock.patch.object(golang, "run")
    def test_go_project_temporarily_stages_root_licence_for_submodules(
        self, run_mock, check_output, _ensure_installed, module_directories
    ):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            module = root / "utils"
            module.mkdir()
            module_directories.return_value = [module]
            (root / "LICENSE").write_text("root licence", encoding="utf8")

            def output(command, **kwargs):
                cwd = Path(kwargs["cwd"])
                if command[:4] == ["go", "list", "-m", "-json"]:
                    self.assertFalse((cwd / "LICENSE").exists())
                    return '{"Path": "example.com/acme"}'

            check_output.side_effect = output

            def run_side_effect(command, **kwargs):
                cwd = Path(kwargs["cwd"])
                self.assertEqual((cwd / "LICENSE").read_text(encoding="utf8"), "root licence")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="github.com/acme/dep\tv1.2.3\thttps://example.com/LICENSE\tMIT\n",
                    stderr="",
                )

            run_mock.side_effect = run_side_effect
            get_value = configuration.get_value
            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(
                configuration,
                "get_value",
                side_effect=lambda key: (
                    "Acme"
                    if key == ConfigurationVariable.PROJECT_NAME
                    else "Apache-2.0" if key == ConfigurationVariable.FILE_LICENCE_IDENTIFIER else get_value(key)
                ),
            ):
                project = golang.GoProjectMetadataFetcher().project_metadata

            self.assertEqual([package.name for package in project.dependencies_metadata], ["github.com/acme/dep"])
            self.assertFalse((module / "LICENSE").exists())

    def test_go_import_paths_have_safe_spdx_filenames_and_ids(self):
        package = SpdxPackage(
            PackageInfo(
                PackageMetadata.from_fields(
                    name="github.com/acme/dep", licence="MIT", licence_source=LicenceSource.TOOL
                ),
                Path("."),
                Path("."),
                "id",
            ),
            is_dependency=True,
        )

        self.assertNotIn("/", package.id)
        filename = SpdxProject._spdx_filename(package.name)
        self.assertEqual(filename, SpdxProject._spdx_filename(package.name))
        self.assertNotIn("/", filename)
        self.assertEqual(SpdxProject._spdx_filename("ordinary-package"), "ordinary-package.spdx")

    def test_go_plugin_supplies_shared_spdx_project(self):
        self.assertTrue(golang.Go().can_get_project_metadata())
        self.assertIsInstance(golang.Go().get_current_spdx_project(), SpdxProject)

    def test_go_import_paths_generate_valid_tag_value_files(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src"
            source.mkdir()
            (source / "main.go").write_text("// SPDX-License-Identifier: MIT\npackage main\n", encoding="utf8")
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[spdx]\nCreatorWebsite = "spdx.org"\nPathToSpdx = "spdxdocs"\nUUID = "go-example"\n',
                encoding="utf8",
            )
            metadata = ProjectMetadata("example.com/acme")
            metadata.project_metadata = PackageMetadata.from_fields(
                name="example.com/acme", licence="MIT", licence_source=LicenceSource.CONFIGURATION
            )
            metadata.add_dependency_metadata(
                PackageMetadata.from_fields(
                    name="github.com/acme/dep", licence="MIT", licence_source=LicenceSource.TOOL
                )
            )
            parser = mock.Mock()
            parser.project_metadata = metadata
            get_value = configuration.get_value
            values = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.SOURCE_DIR: "src",
                ConfigurationVariable.PROJECT_CONFIG: str(project_config),
                ConfigurationVariable.PROJECT_UUID: "go-project-id",
            }
            with mock.patch.object(
                configuration, "get_value", side_effect=lambda key: values[key] if key in values else get_value(key)
            ):
                SpdxProject(parser).generate_tag_value_files(root)

            self.assertEqual(len(list(root.glob("*.spdx"))), 2)
            for spdx_file in root.glob("*.spdx"):
                self.assertEqual(validate_full_spdx_document(parse_file(str(spdx_file))), [])

    def test_go_metadata_uses_shared_spdx_reporting_and_compliance(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src"
            source.mkdir()
            (source / "main.go").write_text("// SPDX-License-Identifier: MIT\npackage main\n", encoding="utf8")
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[spdx]\nCreatorWebsite = "spdx.org"\nPathToSpdx = "spdxdocs"\nUUID = "go-example"\n',
                encoding="utf8",
            )
            project_metadata = ProjectMetadata("example.com/acme")
            project_metadata.project_metadata = PackageMetadata.from_fields(
                name="example.com/acme", version="v1.0.0", licence="MIT", licence_source=LicenceSource.CONFIGURATION
            )
            project_metadata.add_dependency_metadata(
                PackageMetadata.from_fields(
                    name="github.com/acme/dep", version="v1.2.3", licence="MIT", licence_source=LicenceSource.TOOL
                )
            )
            parser = mock.Mock()
            parser.project_metadata = project_metadata
            get_value = configuration.get_value
            paths = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.SOURCE_DIR: "src",
                ConfigurationVariable.PROJECT_CONFIG: str(project_config),
                ConfigurationVariable.PROJECT_UUID: "go-project-id",
            }

            with mock.patch.object(
                configuration, "get_value", side_effect=lambda key: paths[key] if key in paths else get_value(key)
            ):
                project = SpdxProject(parser)
                with mock.patch.object(SpdxProject, "generate_tag_value_file", return_value="sha1") as write_document:
                    project.generate_tag_value_files(root)
                project.generate_licensing_summary(root)
                project.check_licence_compliance()

            self.assertEqual(write_document.call_count, 2)
            for args in write_document.call_args_list:
                self.assertEqual(Path(args.args[2]).name, args.args[2])
            self.assertTrue((root / "third_party_IP_report.html").is_file())
            self.assertIn("github.com/acme/dep", (root / "third_party_IP_report.html").read_text(encoding="utf8"))

            project_metadata.add_dependency_metadata(
                PackageMetadata.from_fields(
                    name="github.com/acme/restricted",
                    licence="GPL-3.0-only",
                    licence_source=LicenceSource.TOOL,
                )
            )
            with mock.patch.object(
                configuration, "get_value", side_effect=lambda key: paths[key] if key in paths else get_value(key)
            ):
                with self.assertRaisesRegex(ValueError, "github.com/acme/restricted"):
                    SpdxProject(parser).check_licence_compliance()


# Mocked unit tests run without Go; only real-tool integration needs both binaries.
@skipUnless(shutil.which("go") and shutil.which("go-licenses"), "Go and go-licenses are required")
class TestGoLicencesIntegration(TestCase):
    def test_real_go_licenses_report_uses_shared_metadata(self):
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir, "project")
            project_root.mkdir()
            (project_root / "go.mod").write_text(
                "module example.com/fixture\n\ngo 1.22\n\nrequire example.com/dependency v0.0.0\n"
                "replace example.com/dependency => ../dependency\n",
                encoding="utf8",
            )
            (project_root / "fixture.go").write_text(
                'package fixture\nimport _ "example.com/dependency"\n', encoding="utf8"
            )
            dependency = Path(temp_dir, "dependency")
            dependency.mkdir()
            (dependency / "go.mod").write_text("module example.com/dependency\n\ngo 1.22\n", encoding="utf8")
            (dependency / "dependency.go").write_text("package dependency\n", encoding="utf8")
            repository_root = Path(__file__).resolve().parents[2]
            licence_text = (repository_root / "LICENSE").read_text(encoding="utf8")
            (project_root / "LICENSE").write_text(licence_text, encoding="utf8")
            (dependency / "LICENSE").write_text(licence_text, encoding="utf8")

            get_value = configuration.get_value
            values = {
                ConfigurationVariable.PROJECT_NAME: "Fixture",
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.SOURCE_DIR: ".",
                ConfigurationVariable.PROJECT_UUID: "go-test-project-id",
            }
            with mock.patch.object(golang, "ROOT_DIR", project_root), mock.patch.object(
                golang, "SRC_DIR", project_root
            ), mock.patch.object(
                configuration, "get_value", side_effect=lambda key: values[key] if key in values else get_value(key)
            ):
                metadata = golang.GoProjectMetadataFetcher().project_metadata

                parser = mock.Mock()
                parser.project_metadata = metadata
                spdx_project = SpdxProject(parser)
                spdx_project.generate_licensing_summary(project_root)
                spdx_project.check_licence_compliance()

            report = (project_root / "third_party_IP_report.html").read_text(encoding="utf8")
            self.assertIn("example.com/dependency", report)

        self.assertEqual(metadata.project_metadata.name, "Fixture")
        self.assertEqual(metadata.project_metadata.licence, "Apache-2.0")
        self.assertEqual([package.name for package in metadata.dependencies_metadata], ["example.com/dependency"])
        self.assertEqual(metadata.dependencies_metadata[0].licence, "Apache-2.0")

    def test_real_go_licenses_report_stages_root_licence_for_submodule(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir, "project")
            root.mkdir()
            module_dir = root / "src"
            module_dir.mkdir()
            (module_dir / "go.mod").write_text(
                "module example.com/fixture\n\ngo 1.22\n\nrequire example.com/dependency v0.0.0\n"
                "replace example.com/dependency => ../dependency\n",
                encoding="utf8",
            )
            (module_dir / "fixture.go").write_text(
                'package fixture\nimport _ "example.com/dependency"\n', encoding="utf8"
            )
            dependency = root / "dependency"
            dependency.mkdir()
            (dependency / "go.mod").write_text("module example.com/dependency\n\ngo 1.22\n", encoding="utf8")
            (dependency / "dependency.go").write_text("package dependency\n", encoding="utf8")
            repository_root = Path(__file__).resolve().parents[2]
            licence_text = (repository_root / "LICENSE").read_text(encoding="utf8")
            (root / "LICENSE").write_text(licence_text, encoding="utf8")
            (dependency / "LICENSE").write_text(licence_text, encoding="utf8")

            get_value = configuration.get_value
            values = {
                ConfigurationVariable.PROJECT_NAME: "Fixture",
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "Apache-2.0",
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.SOURCE_DIR: "src",
                ConfigurationVariable.PROJECT_UUID: "go-test-project-id",
            }
            with mock.patch.object(golang, "ROOT_DIR", root), mock.patch.object(
                golang, "SRC_DIR", module_dir
            ), mock.patch.object(
                configuration, "get_value", side_effect=lambda key: values[key] if key in values else get_value(key)
            ):
                metadata = golang.GoProjectMetadataFetcher().project_metadata

            self.assertFalse((module_dir / "LICENSE").exists())
            self.assertEqual(metadata.project_metadata.name, "Fixture")
            self.assertEqual(metadata.project_metadata.licence, "Apache-2.0")
            self.assertEqual([package.name for package in metadata.dependencies_metadata], ["example.com/dependency"])
            self.assertEqual(metadata.dependencies_metadata[0].licence, "Apache-2.0")
