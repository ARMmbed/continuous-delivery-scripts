#
# Copyright (C) 2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Integration tests for project-level Go module release preparation (offline)."""

import shutil
from pathlib import Path
from unittest import TestCase, mock, skipUnless

from continuous_delivery_scripts.plugins import golang
from continuous_delivery_scripts.tag_and_release import _commit_release_changes, tag_and_release
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory


@skipUnless(shutil.which("go"), "Go is required for module editing")
class TestGoReleaseRequirements(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.path)

    def module(self, directory, name, directives=""):
        path = self.root / directory / "go.mod"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"module {name}\n\ngo 1.22\n{directives}", encoding="utf8")
        return path

    def prepare(self, version="1.3.0", is_new_version=True, source=None):
        with mock.patch.object(golang, "ROOT_DIR", self.root), mock.patch.object(
            golang, "SRC_DIR", source or self.root
        ):
            return golang.Go().prepare_release(self.root, version, is_new_version)

    def test_unchanged_release_does_not_inspect_modules(self):
        self.module(".", "example.com/project")
        with mock.patch.object(golang, "_candidate_go_module_directories") as candidates:
            self.assertEqual(self.prepare(is_new_version=False), [])
        candidates.assert_not_called()

    def test_cds_version_gains_go_prefix_before_editing_requirements(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../core\n",
        )
        self.assertEqual(golang._go_major("1.3.0"), 1)
        with mock.patch.object(golang, "check_call", wraps=golang.check_call) as edit:
            self.assertEqual(self.prepare("1.3.0"), [consumer])
        edit.assert_called_once_with(["go", "mod", "edit", "-require=example.com/core@v1.3.0", str(consumer)])
        self.assertEqual(self.prepare("v1.3.0"), [])
        self.assertIn("example.com/core v1.3.0", consumer.read_text(encoding="utf8"))

    def test_go_major_parses_semantic_and_pseudo_versions(self):
        self.assertEqual(golang._go_major("1.3.0-beta.1"), 1)
        self.assertEqual(golang._go_major("v2.2.0+incompatible"), 2)
        self.assertEqual(golang._go_major("v0.0.0-20220101123456-abcdef123456"), 0)
        with self.assertRaisesRegex(ValueError, "Invalid Go module version"):
            golang._go_major("v2.invalid")

    def test_source_selection_does_not_scan_unrelated_root_modules(self):
        self.module("src/core", "example.com/core")
        unrelated = self.module("elsewhere/consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        invalid = self.root / "elsewhere" / "broken" / "go.mod"
        invalid.parent.mkdir()
        invalid.write_text("not a module\n", encoding="utf8")
        original = unrelated.read_bytes()
        self.assertEqual(self.prepare(source=self.root / "src"), [])
        self.assertEqual(unrelated.read_bytes(), original)

    def test_workspace_selects_modules_outside_source_and_not_unlisted_modules(self):
        source = self.root / "src"
        source.mkdir()
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        unlisted = self.module("src/unlisted", "example.com/unlisted", "\nrequire example.com/core v1.2.0\n")
        self.root.joinpath("go.work").write_text("go 1.22\nuse (\n ./core\n ./consumer\n)\n", encoding="utf8")
        original = unlisted.read_bytes()
        self.assertEqual(self.prepare(source=source), [consumer])
        self.assertEqual(unlisted.read_bytes(), original)

    def test_single_module_and_no_internal_dependencies_are_untouched(self):
        root = self.module(".", "example.com/project", "\nrequire example.com/external/v2 v2.4.0\n")
        original = root.read_bytes()
        self.assertEqual(self.prepare(), [])
        self.assertEqual(root.read_bytes(), original)
        other = self.module("nested/core", "another.org/core", "\nrequire example.com/project/core v1.2.0\n")
        original_other = other.read_bytes()
        self.assertEqual(self.prepare(), [])
        self.assertEqual(root.read_bytes(), original)
        self.assertEqual(other.read_bytes(), original_other)

    def test_internal_requirement_without_local_resolution_remains_unchanged(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        original = consumer.read_bytes()
        self.assertEqual(self.prepare(), [])
        self.assertEqual(consumer.read_bytes(), original)

    def test_only_replaced_internal_requirement_is_updated(self):
        self.module("core", "example.com/core")
        self.module("parser", "example.com/parser")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire (\n example.com/core v1.2.0\n example.com/parser v1.2.0\n)\n"
            "replace example.com/core => ../core\n",
        )
        self.assertEqual(self.prepare(), [consumer])
        content = consumer.read_text(encoding="utf8")
        self.assertIn("example.com/core v1.3.0", content)
        self.assertIn("example.com/parser v1.2.0", content)

    def test_outside_repository_replacement_does_not_qualify(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../../external/core\n",
        )
        original = consumer.read_bytes()
        self.assertEqual(self.prepare(), [])
        self.assertEqual(consumer.read_bytes(), original)

    def test_version_specific_replacement_must_cover_new_version(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core v1.2.0 => ../core\n",
        )
        self.assertEqual(self.prepare(), [])
        self.assertIn("example.com/core v1.2.0", consumer.read_text(encoding="utf8"))
        consumer.write_text(
            consumer.read_text(encoding="utf8").replace(
                "replace example.com/core v1.2.0", "replace example.com/core v1.3.0"
            ),
            encoding="utf8",
        )
        self.assertEqual(self.prepare(), [consumer])
        self.assertIn("require example.com/core v1.3.0", consumer.read_text(encoding="utf8"))

    def test_root_and_nested_modules_direct_indirect_replacements_and_idempotence(self):
        root = self.module(".", "example.com/project")
        core = self.module("core", "example.com/project/core")
        parser = self.module(
            "parser",
            "example.com/project/parser",
            "\nrequire example.com/project/core v1.2.0\nreplace example.com/project/core => ../core\n",
        )
        validator = self.module(
            "validator",
            "example.com/project/validator",
            "\n// keep this comment\nrequire (\n example.com/project/core v1.2.0 // indirect\n"
            " example.com/project/parser v1.3.0\n example.com/third-party/v2 v2.4.0\n)\n"
            "replace (\n example.com/project/core => ../core\n"
            " example.com/project/parser => ../parser\n)\n\ntoolchain go1.22.1\n",
        )
        untouched = {file: file.read_bytes() for file in (root, core)}
        self.assertEqual(self.prepare(), [parser, validator])
        self.assertIn("example.com/project/core v1.3.0", parser.read_text(encoding="utf8"))
        content = validator.read_text(encoding="utf8")
        self.assertIn("example.com/project/core v1.3.0 // indirect", content)
        for fragment in (
            "example.com/project/parser v1.3.0",
            "example.com/third-party/v2 v2.4.0",
            "// keep this comment",
            "toolchain go1.22.1",
            "=> ../core",
            "=> ../parser",
        ):
            self.assertIn(fragment, content)
        updated = {file: file.read_bytes() for file in (parser, validator)}
        self.assertEqual(self.prepare(), [])
        self.assertEqual(updated, {file: file.read_bytes() for file in updated})
        self.assertEqual(untouched, {file: file.read_bytes() for file in untouched})

    def test_no_root_module_with_workspace_and_future_version(self):
        core = self.module("core", "example.com/core")
        consumer = self.module("nested/consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        workspace = self.root / "go.work"
        workspace.write_text(
            "go 1.22\nuse (\n ./core\n ./nested/consumer\n)\n" "replace example.com/core => ./core\n", encoding="utf8"
        )
        work_original = workspace.read_bytes()
        self.assertEqual(self.prepare(), [consumer])
        self.assertIn("example.com/core v1.3.0", consumer.read_text(encoding="utf8"))
        self.assertEqual(workspace.read_bytes(), work_original)
        self.assertEqual(core.read_text(encoding="utf8"), "module example.com/core\n\ngo 1.22\n")

    def test_no_root_module_and_no_workspace_with_grouped_requirements(self):
        self.module("components/engine", "example.com/engine")
        consumer = self.module(
            "components/cli",
            "example.com/cli",
            "\nrequire (\n example.com/engine v1.2.0\n example.com/outside v1.0.0\n)\n"
            "replace example.com/engine => ../engine\n",
        )
        self.assertEqual(self.prepare(), [consumer])
        self.assertIn("example.com/engine v1.3.0", consumer.read_text(encoding="utf8"))

    def test_grouped_workspace_replacements_are_preserved(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        workspace = self.root / "go.work"
        workspace.write_text(
            "go 1.22\nuse (\n ./core\n ./consumer\n)\n" "replace (\n example.com/core => ./core\n)\n",
            encoding="utf8",
        )
        original = workspace.read_bytes()
        self.assertEqual(self.prepare(), [consumer])
        self.assertEqual(workspace.read_bytes(), original)

    def test_workspace_replacement_qualifies_member_without_dependency_in_use(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        self.root.joinpath("go.work").write_text(
            "go 1.22\nuse ./consumer\nreplace example.com/core => ./core\n", encoding="utf8"
        )
        self.assertEqual(self.prepare(source=self.root / "core"), [consumer])

    def test_workspace_use_requires_consumer_to_be_a_member(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        self.root.joinpath("go.work").write_text("go 1.22\nuse ./core\n", encoding="utf8")
        self.assertEqual(self.prepare(source=self.root / "consumer"), [])
        self.assertIn("example.com/core v1.2.0", consumer.read_text(encoding="utf8"))

    def test_nested_workspace_resolves_paths_relative_to_workspace(self):
        self.module("src/core", "example.com/core")
        consumer = self.module("src/consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        workspace = self.root / "src" / "go.work"
        workspace.write_text("go 1.22\nuse (\n ./core\n ./consumer\n)\n", encoding="utf8")
        self.assertEqual(self.prepare(source=self.root / "src"), [consumer])

    def test_missing_or_wrong_local_replace_target_fails_without_changes(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../missing\n",
        )
        original = consumer.read_bytes()
        with self.assertRaisesRegex(ValueError, "Local replacement.*no go.mod"):
            self.prepare()
        self.assertEqual(consumer.read_bytes(), original)
        self.module("missing", "example.com/not-core")
        with self.assertRaisesRegex(ValueError, "Local replacement.*points to"):
            self.prepare()

    def test_missing_workspace_use_and_replace_target(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        workspace = self.root / "go.work"
        workspace.write_text("go 1.22\nuse ./missing\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "references missing module"):
            self.prepare()
        self.assertIn("v1.2.0", consumer.read_text(encoding="utf8"))
        workspace.write_text("go 1.22\nuse ./core\nreplace example.com/core => ./missing\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "Local replacement.*no go.mod"):
            self.prepare()

    def test_missing_external_local_replacement_target(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/outside => ../missing\n",
        )
        with self.assertRaisesRegex(ValueError, "Local replacement.*no go.mod"):
            self.prepare()
        self.assertIn("example.com/core v1.2.0", consumer.read_text(encoding="utf8"))

    def test_duplicate_and_invalid_selected_modules_ignore_outside_source(self):
        self.module("src/core", "example.com/core")
        duplicate = self.module("src/other", "example.com/core")
        with self.assertRaisesRegex(ValueError, "Duplicate Go module declaration"):
            self.prepare(source=self.root / "src")
        duplicate.write_text("not a module\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "Cannot parse"):
            self.prepare(source=self.root / "src")
        duplicate.unlink()
        for name in ("vendor", ".git", ".venv", "build", "dist"):
            self.module(f"{name}/nested", "example.com/core")
        self.assertEqual(self.prepare(source=self.root / "src"), [])

    def test_compatible_major_versions_and_invalid_semantic_import_paths(self):
        self.module("core", "example.com/core/v2")
        consumer = self.module(
            "consumer",
            "example.com/consumer/v2",
            "\nrequire example.com/core/v2 v2.1.0\nreplace example.com/core/v2 => ../core\n",
        )
        with mock.patch.object(golang.logger, "warning") as warning:
            self.assertEqual(self.prepare("2.2.0"), [consumer])
            warning.assert_not_called()
        self.assertIn("example.com/core/v2 v2.2.0", consumer.read_text(encoding="utf8"))

    def test_release_within_major_three_updates_internal_requirement_without_warning(self):
        self.module("core", "example.com/core/v3")
        consumer = self.module(
            "consumer",
            "example.com/consumer/v3",
            "\nrequire example.com/core/v3 v3.4.1\nreplace example.com/core/v3 => ../core\n",
        )
        with mock.patch.object(golang.logger, "warning") as warning:
            self.assertEqual(self.prepare("3.5.0"), [consumer])
            warning.assert_not_called()
        self.assertIn("example.com/core/v3 v3.5.0", consumer.read_text(encoding="utf8"))

    def test_go_module_path_major_uses_semver_for_suffixes(self):
        self.assertEqual(golang._go_module_path_major("example.com/core/v3"), 3)
        self.assertEqual(golang._go_module_path_major("gopkg.in/core.v3"), 3)
        self.assertIsNone(golang._go_module_path_major("example.com/core"))
        self.assertFalse(golang._go_module_path_supports_major("example.com/core/v3", 1))
        self.assertFalse(golang._go_module_path_supports_major("gopkg.in/core.v3", 1))
        self.assertTrue(golang._go_module_path_supports_major("gopkg.in/core.v3", 3))

    def test_gopkg_in_major_three_updates_normally(self):
        self.module("core", "gopkg.in/core.v3")
        consumer = self.module(
            "consumer",
            "example.com/consumer/v3",
            "\nrequire gopkg.in/core.v3 v3.4.1\nreplace gopkg.in/core.v3 => ../core\n",
        )
        self.assertEqual(self.prepare("3.5.0"), [consumer])
        self.assertIn("gopkg.in/core.v3 v3.5.0", consumer.read_text(encoding="utf8"))

    def test_major_three_to_four_requires_module_path_migration(self):
        self.module("core", "example.com/core/v3")
        consumer = self.module(
            "consumer",
            "example.com/consumer/v3",
            "\nrequire example.com/core/v3 v3.4.1\nreplace example.com/core/v3 => ../core\n",
        )
        with mock.patch.object(golang.logger, "warning") as warning:
            with self.assertRaisesRegex(ValueError, "Migrate module declarations"):
                self.prepare("4.0.0")
            warning.assert_called_once()
        self.assertIn("example.com/core/v3 v3.4.1", consumer.read_text(encoding="utf8"))

    def test_major_transition_warns_and_refuses_invalid_version(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../core\n",
        )
        original = consumer.read_bytes()
        with mock.patch.object(golang.logger, "warning") as warning:
            with self.assertRaisesRegex(ValueError, "Migrate module declarations"):
                self.prepare("2.0.0")
            warning.assert_called_once()
        self.assertEqual(consumer.read_bytes(), original)

    def test_invalid_path_for_lower_major_fails(self):
        self.module("core", "example.com/core/v2")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core/v2 v2.1.0\nreplace example.com/core/v2 => ../core\n",
        )
        with self.assertRaisesRegex(ValueError, "module path must match"):
            self.prepare("1.3.0")
        self.assertIn("v2.1.0", consumer.read_text(encoding="utf8"))

    def test_release_commit_stages_prepared_module_files(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../core\n",
        )
        git = mock.Mock(root=self.root)
        files_changed_by_release_preparation = self.prepare()
        with mock.patch(
            "continuous_delivery_scripts.tag_and_release.configuration.get_value", return_value="missing"
        ), mock.patch("continuous_delivery_scripts.tag_and_release._commit_changes"):
            _commit_release_changes(git, "1.3.0", "release", files_changed_by_release_preparation)
        git.add.assert_any_call(consumer)
        self.assertIn("example.com/core v1.3.0", consumer.read_text(encoding="utf8"))

    def test_preparation_precedes_release_documentation(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../core\n",
        )

        def config_value(variable):
            return self.root if str(variable).endswith("PROJECT_ROOT") else False

        def documentation():
            self.assertIn("example.com/core v1.3.0", consumer.read_text(encoding="utf8"))

        with mock.patch.object(golang, "ROOT_DIR", self.root), mock.patch.object(
            golang, "SRC_DIR", self.root
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.get_language_specifics", return_value=golang.Go()
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.configuration.get_value", side_effect=config_value
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.version_project", return_value=(True, "1.3.0", {})
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_documentation", side_effect=documentation
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.insert_licence_header"
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_repository"
        ) as update_repository, mock.patch(
            "continuous_delivery_scripts.tag_and_release._clean_repository"
        ), mock.patch.object(
            golang.Go, "package_software"
        ), mock.patch.object(
            golang.Go, "release_package_to_repository"
        ):
            tag_and_release(CommitType.RELEASE)
        self.assertEqual(update_repository.call_args.args[-1], [consumer])

    def test_no_new_project_version_skips_release_preparation(self):
        self.module("core", "example.com/core")
        consumer = self.module("consumer", "example.com/consumer", "\nrequire example.com/core v1.2.0\n")
        original = consumer.read_bytes()
        with mock.patch.object(golang, "_candidate_go_module_directories") as candidates, mock.patch(
            "continuous_delivery_scripts.tag_and_release.get_language_specifics", return_value=golang.Go()
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.configuration.get_value",
            side_effect=lambda variable: self.root if variable == golang.ConfigurationVariable.PROJECT_ROOT else False,
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.version_project", return_value=(False, "1.3.0", {})
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_documentation"
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.insert_licence_header"
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_repository"
        ) as update_repository:
            tag_and_release(CommitType.RELEASE)
        candidates.assert_not_called()
        self.assertEqual(consumer.read_bytes(), original)
        self.assertEqual(update_repository.call_args.args[-1], [])

    def test_beta_preparation_uses_upcoming_project_version(self):
        self.module("core", "example.com/core")
        consumer = self.module(
            "consumer",
            "example.com/consumer",
            "\nrequire example.com/core v1.2.0\nreplace example.com/core => ../core\n",
        )
        with mock.patch.object(golang, "ROOT_DIR", self.root), mock.patch.object(
            golang, "SRC_DIR", self.root
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.get_language_specifics", return_value=golang.Go()
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.configuration.get_value",
            side_effect=lambda variable: self.root if variable == golang.ConfigurationVariable.PROJECT_ROOT else False,
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.version_project", return_value=(True, "1.3.0-beta.1", {})
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_documentation"
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release.insert_licence_header"
        ), mock.patch(
            "continuous_delivery_scripts.tag_and_release._update_repository"
        ) as update_repository, mock.patch(
            "continuous_delivery_scripts.tag_and_release._clean_repository"
        ), mock.patch.object(
            golang.Go, "package_software"
        ), mock.patch.object(
            golang.Go, "release_package_to_repository"
        ):
            tag_and_release(CommitType.BETA)

        self.assertIn("example.com/core v1.3.0-beta.1", consumer.read_text(encoding="utf8"))
        self.assertEqual(update_repository.call_args.args[-1], [consumer])
