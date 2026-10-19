#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Golang projects."""

import csv
import io
import json
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from subprocess import check_call, check_output, run, CalledProcessError, STDOUT
from tempfile import TemporaryDirectory
from typing import Optional, List, Dict, MutableMapping, Iterator, Set

import semver

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from continuous_delivery_scripts.utils.definitions import CommitType, UNKNOWN
from continuous_delivery_scripts.utils.git_helpers import (
    LocalProjectRepository,
    GitWrapper,
)
from continuous_delivery_scripts.utils.language_specifics_base import (
    BaseLanguage,
    get_language_from_file_name,
)
from continuous_delivery_scripts.utils.package_helpers import (
    LicenceSource,
    PackageMetadata,
    ProjectMetadata,
    ProjectMetadataFetcher,
)

logger = logging.getLogger(__name__)

SRC_DIR = Path(str(configuration.get_value(ConfigurationVariable.SOURCE_DIR)))
ROOT_DIR = Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)))
GO_MOD_FILENAME = "go.mod"
GO_WORK_FILENAME = "go.work"
GO_ALL_PACKAGES_PATTERN = "./..."
ENVVAR_GORELEASER_GIT_TOKEN = "GITHUB_TOKEN"
ENVVAR_GORELEASER_CUSTOMISED_TAG = "GORELEASER_CURRENT_TAG"
ENVVAR_GO_MOD = "GO111MODULE"
ENVVAR_GO_WORK = "GOWORK"
GO_MOD_ON_VALUE = "on"
GO_WORK_OFF_VALUE = "off"
# go-licenses report --template receives Name, Version, LicenseURL and LicenseName for each library.
# https://github.com/google/go-licenses/blob/master/README.md#reports-with-custom-templates
GO_LICENSES_TEMPLATE = "{{range .}}{{.Name}}\t{{.Version}}\t{{.LicenseURL}}\t{{.LicenseName}}\n{{end}}"
LICENCE_FILE_PREFIXES = ("LICENSE", "LICENCE", "COPYING")

# JSON fields returned by `go mod edit -json` and `go work edit -json`.
# https://go.dev/ref/mod#go-mod-edit
# https://go.dev/ref/mod#go-work-edit
GO_JSON_MODULE = "Module"
GO_JSON_REQUIRE = "Require"
GO_JSON_REPLACE = "Replace"
GO_JSON_OLD = "Old"
GO_JSON_NEW = "New"
GO_JSON_PATH = "Path"
GO_JSON_VERSION = "Version"
GO_JSON_USE = "Use"
GO_JSON_DISK_PATH = "DiskPath"


def _go_edit_command(file: Path, subcommand: str, flags: List[str]) -> List[str]:
    """Target an explicit go.mod or go.work, independent of the current directory."""
    return ["go", subcommand, "edit", *flags, str(file)]


def _read_go_metadata_with_edit_command(file: Path, subcommand: str) -> dict:
    """Use Go's parser to inspect directives without resolving unpublished modules."""
    try:
        return json.loads(check_output(_go_edit_command(file, subcommand, ["-json"]), encoding="utf8", stderr=STDOUT))
    except (CalledProcessError, ValueError, OSError) as error:
        detail = error.output if isinstance(error, CalledProcessError) else str(error)
        raise ValueError(f"Cannot parse {file} with Go tooling: {detail}") from error


def _read_go_module_metadata(go_mod_file: Path) -> dict:
    """Read module identity and dependencies without modifying go.mod."""
    return _read_go_metadata_with_edit_command(go_mod_file, "mod")


def _read_go_workspace_metadata(go_work_file: Path) -> dict:
    """Read workspace module selections and replacements without changing go.work."""
    return _read_go_metadata_with_edit_command(go_work_file, "work")


def _release_checkout_path(path: Path, root: Path) -> Path:
    """Map a path chosen by tag discovery to the same location in the release checkout.

    Never prepare modules outside the configured project root, even when a
    workspace happens to reference them.
    """
    source_root = ROOT_DIR.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(source_root):
        raise ValueError(f"Go module path is outside the project root: {path}")
    return root.resolve() / resolved.relative_to(source_root)


def _discover_release_modules(root: Path) -> Dict[str, Path]:
    """Index only tagging's selected modules by their declared import paths.

    Include the root module when present. Exact declared paths, rather than
    repository-relative names or shared prefixes, identify internal dependencies.
    """
    modules: Dict[str, Path] = {}
    for directory in _candidate_go_module_directories(include_project_root=True):
        file = _release_checkout_path(directory, root) / GO_MOD_FILENAME
        if not file.is_file():
            continue
        metadata = _read_go_module_metadata(file)
        name = (metadata.get(GO_JSON_MODULE) or {}).get(GO_JSON_PATH)
        if not name:
            raise ValueError(f"Missing module declaration in {file}")
        if name in modules:
            raise ValueError(f"Duplicate Go module declaration {name!r}: {modules[name]} and {file}")
        modules[name] = file
    return modules


def _release_workspaces(root: Path) -> List[Path]:
    """Locate the root/source workspaces used by tag discovery for validation."""
    return [_release_checkout_path(path, root) for path in _find_go_work_files()]


def _go_major(version: str) -> int:
    """Parse the major component of CDS or Go semver, including pseudo-versions."""
    try:
        return semver.VersionInfo.parse(version.removeprefix("v")).major
    except ValueError as error:
        raise ValueError(f"Invalid Go module version: {version!r}") from error


def _go_module_path_major(module: str) -> Optional[int]:
    """Parse a Go path's /vN (or gopkg.in .vN) semantic import suffix.

    Module paths encode only the major version. Append zero minor and patch
    components so the existing semver parser can validate and extract it.
    See https://go.dev/ref/mod#module-path,
    https://go.dev/doc/modules/major-version and https://semver.org/#spec-item-2.
    """
    separator = ".v" if module.startswith("gopkg.in/") else "/v"
    _, found, major_suffix = module.rpartition(separator)
    if not found:
        return None
    try:
        return _go_major(f"{major_suffix}.0.0")
    except ValueError:
        return None


def _go_module_path_supports_major(module: str, major: int) -> bool:
    """Match v2+ suffixes and reject them for unsuffixed v0/v1 releases."""
    path_major = _go_module_path_major(module)
    if major >= 2:
        return path_major == major
    return path_major is None or path_major < 2


def _check_internal_go_version(module: str, old: str, target: str) -> None:
    """Reject requirements incompatible with the module path before any edits.

    Warn only when a change of major version also requires a manual path and
    import migration; releases within an existing major remain supported.
    """
    target_major = _go_major(target)
    if _go_module_path_supports_major(module, target_major):
        return

    if _go_major(old) != target_major and target_major >= 2:
        logger.warning(
            "Go major-version migration is only partially supported. CDS does not migrate module "
            "declarations, source imports or replace directives. Manual migration is required: "
            "https://go.dev/doc/modules/major-version"
        )
    raise ValueError(
        f"Internal Go module {module!r} cannot require {target}: its module path must match "
        f"major version v{target_major}. Migrate module declarations, imports and requirements before release."
    )


def _validate_local_go_targets(
    metadata: dict, file: Path, modules: Dict[str, Path], root: Path, target_version: str
) -> Set[str]:
    """Return internal modules whose replacements will resolve the target version.

    Check local targets inside the project, but leave replacements pointing
    outside the repository alone. A version-specific replacement for the old
    requirement does not necessarily resolve the upcoming release version.
    """
    locally_replaced: Set[str] = set()
    for replacement in metadata.get(GO_JSON_REPLACE) or []:
        old = replacement[GO_JSON_OLD][GO_JSON_PATH]
        new = replacement[GO_JSON_NEW]
        if new.get(GO_JSON_VERSION):
            continue
        target = (file.parent / new[GO_JSON_PATH]).resolve()
        if not target.is_relative_to(root.resolve()):
            continue
        if not (target / GO_MOD_FILENAME).is_file():
            raise ValueError(f"Local replacement for {old} in {file} has no {GO_MOD_FILENAME} at {target}")
        if old in modules and target != modules[old].parent.resolve():
            raise ValueError(f"Local replacement for {old} in {file} points to {target}, not {modules[old].parent}")
        if old in modules and replacement[GO_JSON_OLD].get(GO_JSON_VERSION) in (None, "", target_version):
            locally_replaced.add(old)
    return locally_replaced


def _plan_internal_go_requirement_updates(
    modules: Dict[str, Path], workspace_modules: Dict[Path, Set[str]], root: Path, target_version: str
) -> Dict[Path, List[str]]:
    """Plan edits after exact path matching, before touching any go.mod files.

    Update only requirements resolved through a repository-local replacement
    or through a workspace containing the requiring and required modules.
    """
    changes: Dict[Path, List[str]] = {}
    for module_file in modules.values():
        metadata = _read_go_module_metadata(module_file)
        locally_resolved = _validate_local_go_targets(metadata, module_file, modules, root, target_version)
        locally_resolved.update(workspace_modules.get(module_file, set()))
        outdated = []
        for requirement in metadata.get(GO_JSON_REQUIRE) or []:
            path = requirement[GO_JSON_PATH]
            if path in locally_resolved:
                _check_internal_go_version(path, requirement[GO_JSON_VERSION], target_version)
                if requirement[GO_JSON_VERSION] != target_version:
                    outdated.append(path)
        if outdated:
            changes[module_file] = sorted(outdated)
    return changes


def _validate_go_release_workspaces(root: Path, modules: Dict[str, Path], target_version: str) -> Dict[Path, Set[str]]:
    """Find internal modules locally available to each workspace member."""
    available_by_module: Dict[Path, Set[str]] = {}
    for workspace in _release_workspaces(root):
        work_metadata = _read_go_workspace_metadata(workspace)
        replaced = _validate_local_go_targets(work_metadata, workspace, modules, root, target_version)
        used_directories = set()
        for use in work_metadata.get(GO_JSON_USE) or []:
            directory = (workspace.parent / use[GO_JSON_DISK_PATH]).resolve()
            if not (directory / GO_MOD_FILENAME).is_file():
                raise ValueError(f"Go workspace {workspace} references missing module at {directory}")
            if directory.is_relative_to(root.resolve()):
                used_directories.add(directory)
        available = replaced | {name for name, file in modules.items() if file.parent.resolve() in used_directories}
        for file in modules.values():
            if file.parent.resolve() in used_directories:
                available_by_module.setdefault(file, set()).update(available)
    return available_by_module


def _update_internal_go_requirements(file: Path, paths: List[str], target_version: str) -> None:
    """Apply only planned require changes using Go tooling, without go get or tidy."""
    logger.info("Updating internal Go requirements in %s to %s", file, target_version)
    try:
        check_call(_go_edit_command(file, "mod", [f"-require={path}@{target_version}" for path in paths]))
    except (CalledProcessError, OSError) as error:
        raise ValueError(f"Cannot update internal Go requirements in {file}: {error}") from error


def _prepare_go_module_requirements(root: Path, target_version: str) -> List[Path]:
    """Validate all selected modules, then update their internal requirements.

    Return only changed go.mod paths so CDS can stage them in its release
    commit; a single-module project has no internal dependencies to update.
    """
    modules = _discover_release_modules(root)
    workspace_modules = _validate_go_release_workspaces(root, modules, target_version)
    changes = _plan_internal_go_requirement_updates(modules, workspace_modules, root, target_version)
    if len(modules) < 2:
        return []

    for file, paths in changes.items():
        _update_internal_go_requirements(file, paths, target_version)
    return list(changes)


def _generate_doc2go_command_list(executable: str, output_directory: Path, patterns: List[str]) -> List[str]:
    return [
        executable,
        "-out",
        str(output_directory),
        *patterns,
    ]


def _generate_goreleaser_release_command_list(changelog: Path) -> List[str]:
    return [
        "goreleaser",
        "release",
        "--clean",
        "--release-notes",
        f"{str(changelog)}",
    ]


def _generate_goreleaser_check_command_list() -> List[str]:
    return [
        "goreleaser",
        "check",
    ]


def _install_doc2go_command_list() -> List[str]:
    return [
        "go",
        "install",
        "go.abhg.dev/doc2go@latest",
    ]


def _install_syft_command_list() -> List[str]:
    return ["go", "install", "github.com/anchore/syft/cmd/syft@latest"]


def _install_goreleaser_command_list() -> List[str]:
    return ["go", "install", "github.com/goreleaser/goreleaser/v2@latest"]


def _install_go_licenses_command_list() -> List[str]:
    return ["go", "install", "github.com/google/go-licenses/v2@latest"]


def _installed_go_tool_path(tool_name: str, env: MutableMapping[str, str]) -> str:
    """Find a binary installed using go install, even when Go's bin directory is not on PATH."""
    go_bin = check_output(["go", "env", "GOBIN"], env=env, encoding="utf8").strip()
    if not go_bin:
        go_path = check_output(["go", "env", "GOPATH"], env=env, encoding="utf8").strip()
        go_bin = str(Path(go_path.split(os.pathsep)[0]) / "bin")
    executable = Path(go_bin) / (f"{tool_name}.exe" if os.name == "nt" else tool_name)
    if not executable.is_file():
        raise FileNotFoundError(f"Could not find installed {tool_name} binary: {executable}")
    return str(executable)


def _candidate_go_module_directories(include_project_root: bool = False) -> List[Path]:
    """Share module selection between release tags and licence reporting."""
    candidates = [SRC_DIR]
    if include_project_root:
        candidates.append(ROOT_DIR)
    workspace_modules = _determine_go_work_module_directories()
    candidates.extend(workspace_modules if workspace_modules else _determine_go_subproject_directories())
    return list(dict.fromkeys(candidates))


def _go_licence_module_directories() -> List[Path]:
    """Find actual Go modules for dependency reporting."""
    modules = [
        path
        for path in _candidate_go_module_directories(include_project_root=True)
        if (path / GO_MOD_FILENAME).is_file()
    ]
    if not modules:
        raise FileNotFoundError(f"No {GO_MOD_FILENAME} found in {SRC_DIR}, {ROOT_DIR} or their Go workspace modules.")
    return modules


def _go_module_name(module_dir: Path, env: MutableMapping[str, str]) -> str:
    """Read the import path declared by a Go module."""
    # `go list -m -json` emits one JSON document per main module when a go.work
    # workspace is active. Disable workspace mode here so CDS always reads the
    # module declared by `module_dir` rather than the whole workspace.
    module_env = dict(env)
    module_env[ENVVAR_GO_WORK] = GO_WORK_OFF_VALUE
    module = json.loads(check_output(["go", "list", "-m", "-json"], cwd=module_dir, env=module_env, encoding="utf8"))
    return str(module[GO_JSON_PATH])


def _download_go_module_dependencies(module_directories: List[Path], env: MutableMapping[str, str]) -> None:
    """Download Go dependencies for each detected module.

    `go-licenses` expects the module graph to be available locally. Fetching the
    dependencies here means callers do not need a separate CI step before
    running `cd-check-licence-compliance` or `cd-generate-spdx`.
    """
    for module_directory in module_directories:
        logger.info("Downloading Go module dependencies in [%s].", module_directory)
        check_call(["go", "mod", "download", "all"], cwd=module_directory, env=env)


def _should_download_go_module_dependencies() -> bool:
    """Return whether Go module dependencies should be prefetched automatically."""
    configured = configuration.get_value_or_default(ConfigurationVariable.SKIP_DEPENDENCY_DOWNLOAD_FOR_LICENSING, False)
    if isinstance(configured, str):
        configured = configured.strip().lower() in ("true", "1", "yes", "on")
    return not bool(configured)


def _parse_go_licences(output: str) -> List[PackageMetadata]:
    """Translate go-licenses template output into shared package metadata."""
    packages = []
    for row in csv.reader(io.StringIO(output), delimiter="\t"):
        if len(row) != 4 or not row[0].strip():
            raise ValueError(f"Unexpected go-licenses report row: {row}")
        name, version, licence_url, licence = (item.strip() for item in row)
        known_licence = bool(licence and licence.lower() != UNKNOWN)
        evidence = [{"kind": "licence", "path": licence_url, "text": ""}] if licence_url.startswith("https://") else []
        packages.append(
            PackageMetadata.from_fields(
                name=name,
                version=version or UNKNOWN,
                licence=licence if known_licence else UNKNOWN,
                licence_source=LicenceSource.TOOL if known_licence else LicenceSource.UNKNOWN,
                declared_licence=licence or UNKNOWN,
                url=licence_url or UNKNOWN,
                licence_evidence=evidence,
            )
        )
    return packages


def _log_go_licenses_stderr(module_dir: Path, stderr_output: str) -> None:
    """Report go-licenses diagnostics through CDS logging instead of leaking raw stderr."""
    diagnostics = stderr_output.strip()
    if not diagnostics:
        return
    logger.warning(
        "go-licenses emitted diagnostics while scanning [%s]. Re-run with -vv for the captured stderr.",
        module_dir,
    )
    logger.info("go-licenses stderr for [%s]:\n%s", module_dir, diagnostics)


def _run_go_licenses_report(
    executable: str, module_dir: Path, template_path: Path, env: MutableMapping[str, str]
) -> str:
    """Run go-licenses with captured stderr so CDS controls when diagnostics are shown."""
    result = run(
        [executable, "report", GO_ALL_PACKAGES_PATTERN, "--template", str(template_path)],
        cwd=module_dir,
        env=env,
        encoding="utf8",
        capture_output=True,
        check=False,
    )
    _log_go_licenses_stderr(module_dir, result.stderr)
    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=error_message)
    return result.stdout


def _find_licence_file(directory: Path) -> Optional[Path]:
    """Return the first recognised licence file in a directory."""
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name.upper().startswith(LICENCE_FILE_PREFIXES):
            return path
    return None


@contextmanager
def _stage_root_licence_files_for_modules(module_directories: List[Path]) -> Iterator[None]:
    """Temporarily copy the root licence into module directories that do not already have one."""
    root_licence_file = _find_licence_file(ROOT_DIR)
    if not root_licence_file:
        yield
        return

    staged_files: List[Path] = []
    try:
        for module_directory in module_directories:
            if module_directory == ROOT_DIR or _find_licence_file(module_directory):
                continue
            # go-licenses only searches for licence files up to the module root, so
            # nested modules cannot see a repository-level LICENSE on their own.
            destination = module_directory / root_licence_file.name
            shutil.copy2(root_licence_file, destination)
            staged_files.append(destination)
        yield
    finally:
        # Remove only the temporary copies we created so existing module-specific
        # licence files remain untouched and the worktree stays clean.
        for staged_file in staged_files:
            staged_file.unlink(missing_ok=True)


class GoProjectMetadataFetcher(ProjectMetadataFetcher):
    """Retrieve Go dependency licences for the shared SPDX and compliance report."""

    def __init__(self, skip_dependency_download: bool = False) -> None:
        """Initialise with the configured project name."""
        super().__init__(str(configuration.get_value(ConfigurationVariable.PROJECT_NAME)))
        self._skip_dependency_download = skip_dependency_download

    def fetch_project_metadata(self) -> ProjectMetadata:
        """Collect module dependencies using go-licenses without replacing shared policy checks."""
        module_directories = _go_licence_module_directories()
        env = os.environ.copy()
        env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
        if not self._skip_dependency_download and _should_download_go_module_dependencies():
            _download_go_module_dependencies(module_directories, env)
        else:
            logger.info("Skipping Go module dependency downloads before licence analysis by configuration.")
        executable = _ensure_go_tool_installed(
            tool_name="go-licenses",
            version_command=["go-licenses", "report", "--help"],
            install_command=_install_go_licenses_command_list(),
            env=env,
        )
        project = ProjectMetadata(self._package_name)
        project.project_metadata = PackageMetadata.from_fields(
            name=self._package_name,
            licence=str(configuration.get_value(ConfigurationVariable.FILE_LICENCE_IDENTIFIER)),
            licence_source=LicenceSource.CONFIGURATION,
        )
        dependencies: Dict[str, PackageMetadata] = {}
        modules = [(module_dir, _go_module_name(module_dir, env)) for module_dir in module_directories]
        with TemporaryDirectory() as temporary_dir:
            template_path = Path(temporary_dir) / "go-licenses.tpl"
            template_path.write_text(GO_LICENSES_TEMPLATE, encoding="utf8")
            with _stage_root_licence_files_for_modules(module_directories):
                for module_dir, _ in modules:
                    output = _run_go_licenses_report(executable, module_dir, template_path, env)
                    for package in _parse_go_licences(output):
                        if any(package.name == name or package.name.startswith(f"{name}/") for _, name in modules):
                            continue
                        existing = dependencies.get(package.name)
                        if existing and (existing.version, existing.licence) != (package.version, package.licence):
                            candidates = existing.licence_candidates or [existing.licence]
                            dependencies[package.name] = PackageMetadata.from_fields(
                                name=package.name,
                                version=UNKNOWN if existing.version != package.version else package.version,
                                licence=UNKNOWN,
                                licence_source=LicenceSource.UNKNOWN,
                                licence_candidates=sorted(set(candidates + [package.licence])),
                                licence_evidence=existing.licence_evidence + package.licence_evidence,
                            )
                        elif existing is None:
                            dependencies[package.name] = package
        for dependency in dependencies.values():
            project.add_dependency_metadata(dependency)
        return project


def _ensure_go_tool_installed(
    tool_name: str,
    version_command: List[str],
    install_command: List[str],
    env: MutableMapping[str, str],
) -> str:
    """Return a usable Go tool on PATH or install it into the Go binary directory."""
    tool_path = shutil.which(tool_name)
    if tool_path:
        try:
            check_output(version_command, env=env)
            logger.info("Using %s from PATH: %s", tool_name, tool_path)
            return tool_path
        except Exception as exception:
            logger.warning("Could not use %s from PATH: %s", tool_name, exception)

    logger.info("Installing %s with go install.", tool_name)
    check_call(install_command, env=env)
    return _installed_go_tool_path(tool_name, env)


def _doc2go_target(module: str) -> tuple[Path, List[str]]:
    """Resolve MODULE_TO_DOCUMENT to a Go module, package or explicit pattern."""
    requested = module.strip()
    if not requested:
        raise ValueError("MODULE_TO_DOCUMENT must identify the Go module or package to document")

    root = ROOT_DIR.resolve()
    source = SRC_DIR.resolve()
    modules = list(
        dict.fromkeys(
            directory.resolve()
            for directory in _candidate_go_module_directories(include_project_root=True)
            if (directory / GO_MOD_FILENAME).is_file()
        )
    )

    if requested == ".":
        workspace_modules = list(
            dict.fromkeys(
                directory.resolve()
                for directory in _determine_go_work_module_directories()
                if (directory / GO_MOD_FILENAME).is_file() and directory.resolve().is_relative_to(root)
            )
        )
        if workspace_modules:
            return root, [
                GO_ALL_PACKAGES_PATTERN if directory == root else f"./{directory.relative_to(root).as_posix()}/..."
                for directory in workspace_modules
            ]
        if (root / GO_MOD_FILENAME).is_file():
            return root, [GO_ALL_PACKAGES_PATTERN]
        raise FileNotFoundError(f"No Go module or workspace found at {ROOT_DIR}")

    matches = []
    for directory in modules:
        relative = directory.relative_to(root).as_posix() if directory.is_relative_to(root) else None
        if requested in {directory.name, str(directory), relative, f"./{relative}"}:
            matches.append(directory)
    project_module = (root / requested).resolve()
    if (
        project_module.is_relative_to(root)
        and (project_module / GO_MOD_FILENAME).is_file()
        and project_module not in matches
    ):
        matches.append(project_module)
    if len(matches) > 1:
        raise ValueError(f"MODULE_TO_DOCUMENT={requested!r} matches several Go modules; use a project-relative path")
    if matches:
        return matches[0], [GO_ALL_PACKAGES_PATTERN]

    # Package directories can be named relative to the project or source root.
    package_matches = []
    for candidate in ((root / requested).resolve(), (source / requested).resolve()):
        if candidate.is_dir():
            containing_modules = [directory for directory in modules if candidate.is_relative_to(directory)]
            if containing_modules:
                directory = max(containing_modules, key=lambda path: len(path.parts))
                relative = candidate.relative_to(directory).as_posix()
                result = directory, [f"./{relative}/..."]
                if result not in package_matches:
                    package_matches.append(result)
    if len(package_matches) > 1:
        raise ValueError(f"MODULE_TO_DOCUMENT={requested!r} matches several Go packages; use a project-relative path")
    if package_matches:
        return package_matches[0]

    # A source subdirectory of a module can also be selected by its short name.
    if requested == source.name and any((parent / GO_MOD_FILENAME).is_file() for parent in (source, *source.parents)):
        return source, [GO_ALL_PACKAGES_PATTERN]

    # Recognise a full module path without requiring the caller to append /....
    if "." in requested and not requested.startswith("./"):
        env = os.environ.copy()
        for directory in modules:
            import_path = _go_module_name(directory, env)
            if requested in {import_path, f"{import_path}/..."}:
                return directory, [GO_ALL_PACKAGES_PATTERN]

    # An explicit package import path or Go package pattern is used as supplied.
    return source, [requested]


def _call_doc2go(output_directory: Path, module: str) -> None:
    """Call doc2go for generating the docs."""
    working_dir, patterns = _doc2go_target(module)
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    executable = _ensure_go_tool_installed(
        tool_name="doc2go",
        version_command=["doc2go", "-version"],
        install_command=_install_doc2go_command_list(),
        env=env,
    )
    logger.info("Creating Code documentation.")
    logger.info("Running doc2go over [%s] in [%s].", patterns, working_dir)
    check_call(
        _generate_doc2go_command_list(executable, output_directory.resolve(), patterns),
        cwd=str(working_dir),
        env=env,
    )


def _call_goreleaser_check(version: str) -> None:
    """Calls go releaser check to verify configuration."""
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    _ensure_go_tool_installed(
        tool_name="syft",
        version_command=["syft", "--version"],
        install_command=_install_syft_command_list(),
        env=env,
    )
    _ensure_go_tool_installed(
        tool_name="goreleaser",
        version_command=["goreleaser", "--version"],
        install_command=_install_goreleaser_command_list(),
        env=env,
    )
    logger.info("Checking GoReleaser configuration.")
    env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = version
    env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    check_call(_generate_goreleaser_check_command_list(), cwd=ROOT_DIR, env=env)


def _determine_go_module_tag_for_directory(module_directory: Path, version: str) -> Optional[str]:
    try:
        module = module_directory.relative_to(ROOT_DIR)
    except ValueError:
        try:
            module = ROOT_DIR.relative_to(module_directory)
        except ValueError as exception:
            logger.warning(exception)
            return None
    module_as_posix = module.as_posix().rstrip("/")
    if module_as_posix == "." or len(module_as_posix) == 0:
        return None
    return f"{module_as_posix}/{version}"


def _find_go_work_files() -> List[Path]:
    go_work_files: List[Path] = []
    for go_work_file in [SRC_DIR.joinpath(GO_WORK_FILENAME), ROOT_DIR.joinpath(GO_WORK_FILENAME)]:
        if go_work_file.exists() and go_work_file not in go_work_files:
            go_work_files.append(go_work_file)
    return go_work_files


def _determine_go_work_module_directories_from_json(go_work_file: Path) -> List[Path]:
    """Determine module directories from `go work edit -json` output.

    `go.work` lists all workspace modules that should be released together.
    See https://go.dev/ref/mod#workspaces and https://pkg.go.dev/cmd/go#hdr-Edit_workspace_file.
    """
    go_work_root = go_work_file.parent
    go_work = _read_go_workspace_metadata(go_work_file)
    module_directories: List[Path] = []
    for use_definition in go_work.get(GO_JSON_USE, []):
        disk_path = use_definition.get(GO_JSON_DISK_PATH) or use_definition.get(GO_JSON_PATH)
        if not disk_path:
            continue
        module_directory = Path(str(disk_path))
        module_directories.append(
            module_directory if module_directory.is_absolute() else go_work_root.joinpath(module_directory)
        )
    return module_directories


def _determine_go_work_module_directories() -> List[Path]:
    """Determine module directories declared in `go.work`.

    `go.work` lists all workspace modules that should be released together.
    See https://go.dev/ref/mod#workspaces.
    """
    module_directories: List[Path] = []
    for go_work_file in _find_go_work_files():
        module_directories.extend(_determine_go_work_module_directories_from_json(go_work_file))
    return list(dict.fromkeys(module_directories))


def _determine_go_subproject_directories() -> List[Path]:
    if not SRC_DIR.exists():
        return []
    return sorted((go_mod_file.parent for go_mod_file in SRC_DIR.rglob(GO_MOD_FILENAME)), key=lambda path: str(path))


def _determine_go_module_tag(version: str) -> List[str]:
    """Determine all go module tags for release.

    See https://golang.org/ref/mod#vcs-version,
    https://go.dev/ref/mod#workspaces, and
    https://github.com/golang/go/wiki/Modules/a549b3e4b7ad6be6e7d11c37ef247bb2279c8146#faqs--multi-module-repositories.
    """
    tags = [
        _determine_go_module_tag_for_directory(module_directory, version)
        for module_directory in _candidate_go_module_directories()
    ]
    return list(dict.fromkeys([tag for tag in tags if tag]))


class Go(BaseLanguage):
    """Specific actions for a Golang project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return str(get_language_from_file_name(__file__))

    def get_version_tag(self, version: str) -> str:
        """Gets tag based on version."""
        cleansed_version = version.strip().lstrip("v")
        return f"v{cleansed_version}"

    def prepare_release(self, root: Path, version: str, is_new_version: bool) -> List[Path]:
        """Synchronise internal requirements only for a new project release."""
        if not is_new_version:
            return []
        return _prepare_go_module_requirements(root, self.get_version_tag(version))

    def package_software(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().package_software(mode, version)
        _call_goreleaser_check(version)

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """No operation."""
        super().release_package_to_repository(mode, version)
        self._call_goreleaser_release(version)

    def check_credentials(self) -> None:
        """Checks any credentials."""
        super().check_credentials()
        configuration.get_value(ConfigurationVariable.GIT_TOKEN)

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Generates the code documentation."""
        super().generate_code_documentation(output_directory, module_to_document)
        _call_doc2go(output_directory, module_to_document)

    def can_add_licence_headers(self) -> bool:
        """States that licence headers can be added."""
        return True

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return True

    def get_secret_registry_exclude_files(self) -> List[str]:
        """Gets additional detect-secrets exclude patterns for Go projects."""
        return [
            r".*go\.sum$",
            r"^\.circleci[\\/].*",
            r"^workflows/.*",
            (r"^\.github[\\/]workflows[\\/].*"),
        ]

    def get_current_spdx_project(self, skip_dependency_download: bool = False) -> Optional[SpdxProject]:
        """Gets current SPDX description."""
        return SpdxProject(GoProjectMetadataFetcher(skip_dependency_download=skip_dependency_download))

    def should_clean_before_packaging(self) -> bool:
        """States whether the repository must be cleaned before packaging happens."""
        return True

    def tag_release(self, git: GitWrapper, version: str, shortcuts: Dict[str, bool]) -> None:
        """Tags release commit."""
        super().tag_release(git, version, shortcuts)
        for go_tag in _determine_go_module_tag(self.get_version_tag(version)):
            git.create_tag(go_tag, message=f"Golang module release: {go_tag}")

    def _call_goreleaser_release(self, version: str) -> None:
        """Calls go releaser release to upload packages."""
        env = os.environ
        env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
        _ensure_go_tool_installed(
            tool_name="syft",
            version_command=["syft", "--version"],
            install_command=_install_syft_command_list(),
            env=env,
        )
        _ensure_go_tool_installed(
            tool_name="goreleaser",
            version_command=["goreleaser", "--version"],
            install_command=_install_goreleaser_command_list(),
            env=env,
        )
        tag = self.get_version_tag(version)
        # The tag of the release must be retrieved
        # See https://github.com/goreleaser/goreleaser/discussions/1426
        logger.info(f"Checking out tag: {tag}.")
        with LocalProjectRepository() as git:
            git.configure_for_github()
            git.fetch()
            git.checkout(f"tags/{tag}")
        logger.info("Release package.")
        changelogPath = configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH)
        env[ENVVAR_GORELEASER_CUSTOMISED_TAG] = tag
        env[ENVVAR_GORELEASER_GIT_TOKEN] = configuration.get_value(ConfigurationVariable.GIT_TOKEN)
        check_call(
            _generate_goreleaser_release_command_list(changelogPath),
            cwd=ROOT_DIR,
            env=env,
        )
