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
from subprocess import check_call, check_output, run, CalledProcessError
from tempfile import TemporaryDirectory
from typing import Optional, List, Dict, MutableMapping, Iterator

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


def _generate_doc2go_command_list(executable: str, output_directory: Path, module: str) -> List[str]:
    return [
        executable,
        "-out",
        str(output_directory),
        f"{module}",
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
        path for path in _candidate_go_module_directories(include_project_root=True) if (path / "go.mod").is_file()
    ]
    if not modules:
        raise FileNotFoundError(f"No go.mod found in {SRC_DIR}, {ROOT_DIR} or their Go workspace modules.")
    return modules


def _go_module_name(module_dir: Path, env: MutableMapping[str, str]) -> str:
    """Read the import path declared by a Go module."""
    # `go list -m -json` emits one JSON document per main module when a go.work
    # workspace is active. Disable workspace mode here so CDS always reads the
    # module declared by `module_dir` rather than the whole workspace.
    module_env = dict(env)
    module_env[ENVVAR_GO_WORK] = GO_WORK_OFF_VALUE
    module = json.loads(check_output(["go", "list", "-m", "-json"], cwd=module_dir, env=module_env, encoding="utf8"))
    return str(module["Path"])


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
        [executable, "report", "./...", "--template", str(template_path)],
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


def _call_doc2go(output_directory: Path, module: str) -> None:
    """Call doc2go for generating the docs."""
    env = os.environ
    env[ENVVAR_GO_MOD] = GO_MOD_ON_VALUE
    executable = _ensure_go_tool_installed(
        tool_name="doc2go",
        version_command=["doc2go", "-version"],
        install_command=_install_doc2go_command_list(),
        env=env,
    )
    logger.info("Creating Code documentation.")
    logger.info("Running doc2go over [%s] in [%s].", module, SRC_DIR)
    check_call(
        _generate_doc2go_command_list(executable, output_directory, module),
        cwd=str(SRC_DIR),
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
    for go_work_file in [SRC_DIR.joinpath("go.work"), ROOT_DIR.joinpath("go.work")]:
        if go_work_file.exists() and go_work_file not in go_work_files:
            go_work_files.append(go_work_file)
    return go_work_files


def _determine_go_work_module_directories_from_json(go_work_file: Path) -> List[Path]:
    """Determine module directories from `go work edit -json` output.

    `go.work` lists all workspace modules that should be released together.
    See https://go.dev/ref/mod#workspaces and https://pkg.go.dev/cmd/go#hdr-Edit_workspace_file.
    """
    go_work_root = go_work_file.parent
    go_work = json.loads(check_output(["go", "work", "edit", "-json"], cwd=go_work_root, encoding="utf8"))
    module_directories: List[Path] = []
    for use_definition in go_work.get("Use", []):
        disk_path = use_definition.get("DiskPath") or use_definition.get("Path")
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
    return sorted((go_mod_file.parent for go_mod_file in SRC_DIR.rglob("go.mod")), key=lambda path: str(path))


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
        _call_doc2go(output_directory, module_to_document if module_to_document else "./...")

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
