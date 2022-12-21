#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Orchestrates release process."""
import argparse
import datetime
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict

from continuous_delivery_scripts.generate_docs import generate_documentation
from continuous_delivery_scripts.generate_news import version_project
from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.license_files import insert_licence_header
from continuous_delivery_scripts.report_third_party_ip import generate_spdx_project_reports, SpdxProject
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import ProjectTempClone, LocalProjectRepository, GitWrapper
from continuous_delivery_scripts.utils.logging import log_exception, set_log_level
from continuous_delivery_scripts.utils.versioning import determine_version_shortcuts

SPDX_REPORTS_DIRECTORY = "licensing"

logger = logging.getLogger(__name__)


def tag_and_release(mode: CommitType, current_branch: Optional[str] = None) -> None:
    """Tags and releases.

    Updates repository with changes and releases package to PyPI for general availability.

    Args:
        mode: release mode
        current_branch: current branch in case the current branch cannot easily
        be determined (e.g. on CI)

    """
    get_language_specifics().check_credentials()
    is_new_version, version, version_elements = version_project(mode)
    logger.info(f"Current version: {version}")
    if not version:
        raise ValueError("Undefined version.")
    if mode == CommitType.DEVELOPMENT:
        return
    # The documentation folder will be emptied when the documentation is updated
    _update_documentation()
    # Adding the licensing summaries in /docs after folder has been cleared and regenerated.
    spdx_project = _update_licensing_summary()
    insert_licence_header(0)
    _update_repository(mode, is_new_version, version, current_branch, version_elements)
    if is_new_version:
        if get_language_specifics().should_clean_before_packaging():
            _clean_repository()
        if spdx_project and get_language_specifics().should_include_spdx_in_package():
            _generate_spdx_reports(spdx_project)
        get_language_specifics().package_software(mode, version)
        get_language_specifics().release_package_to_repository(mode, version)


def _get_documentation_config() -> Tuple[Path, str]:
    docs_dir = Path(configuration.get_value(ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH))
    module_to_document = configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)

    return docs_dir, module_to_document


def _update_documentation() -> None:
    """Ensures the documentation is in the correct location for releasing."""
    docs_dir, module_to_document = _get_documentation_config()
    generate_documentation(docs_dir, module_to_document)


def _update_licensing_summary() -> Optional[SpdxProject]:
    if not get_language_specifics().can_get_project_metadata():
        return None

    project = get_language_specifics().get_current_spdx_project()
    if project:
        project.generate_licensing_summary(
            Path(configuration.get_value(ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH))
        )
    return project


def _update_repository(
    mode: CommitType,
    is_new_version: bool,
    version: str,
    current_branch: Optional[str],
    version_elements: Dict[str, str],
) -> None:
    """Update repository with changes that happened."""
    with ProjectTempClone(desired_branch_name=current_branch) as git:
        git.configure_for_github()
        time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        commit_message = f"🚀 releasing version {version} @ {time_str}" if is_new_version else "📰 Automatic changes ⚙"
        if mode == CommitType.RELEASE:
            _commit_release_changes(git, version, commit_message)
        if is_new_version:
            get_language_specifics().tag_release(
                git,
                version,
                determine_version_shortcuts(
                    mode,
                    configuration.get_value(ConfigurationVariable.TAG_LATEST),
                    configuration.get_value(ConfigurationVariable.TAG_VERSION_SHORTCUTS),
                    version_elements,
                ),
            )
            git.force_push_tag()


def _clean_repository() -> None:
    """Cleans the local repository."""
    with LocalProjectRepository() as git:
        logger.info("Cleaning repository")
        git.stash()
        git.clean()
        git.fetch()
        git.pull()
        git.clean()


def _generate_spdx_reports(project: SpdxProject) -> None:
    report_directory = Path(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)).joinpath(
        SPDX_REPORTS_DIRECTORY
    )
    report_directory.mkdir(exist_ok=True)
    generate_spdx_project_reports(project, report_directory)


def _add_version_changes(git: GitWrapper) -> None:
    git.add(configuration.get_value(ConfigurationVariable.VERSION_FILE_PATH))
    git.add(configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH))
    git.add(configuration.get_value(ConfigurationVariable.NEWS_DIR))


def _commit_release_changes(git: GitWrapper, version: str, commit_message: str) -> None:
    logger.info(f"Committing release [{version}]...")
    git.add(configuration.get_value(ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH))
    _add_version_changes(git)
    _commit_changes(commit_message, git)


def _commit_changes(commit_message: str, git: GitWrapper) -> None:
    git.commit(f"{commit_message}\n[skip ci]")
    git.push()
    git.pull()


def main() -> None:
    """Commands.

    Returns:
        success code (0) if successful; failure code otherwise.
    """
    parser = argparse.ArgumentParser(description="Releases the project.")
    parser.add_argument(
        "-t", "--release-type", help="type of release to perform", required=True, type=str, choices=CommitType.choices()
    )
    parser.add_argument("-b", "--current-branch", help="Name of the current branch", nargs="?")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        tag_and_release(CommitType.parse(args.release_type), args.current_branch)
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
