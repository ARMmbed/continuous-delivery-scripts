#
# Copyright (c) 2020, Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Orchestrates release process."""
import sys

import argparse
import datetime
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from mbed_tools_ci_scripts.generate_docs import generate_documentation
from mbed_tools_ci_scripts.generate_news import version_project
from mbed_tools_ci_scripts.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci_scripts.utils.definitions import CommitType
from mbed_tools_ci_scripts.utils.filesystem_helpers import cd
from mbed_tools_ci_scripts.utils.git_helpers import ProjectTempClone, GitWrapper
from mbed_tools_ci_scripts.utils.logging import log_exception, set_log_level

ENVVAR_TWINE_USERNAME = "TWINE_USERNAME"
ENVVAR_TWINE_PASSWORD = "TWINE_PASSWORD"
OUTPUT_DIRECTORY = "release-dist"

logger = logging.getLogger(__name__)


def tag_and_release(mode: CommitType, current_branch: Optional[str] = None) -> None:
    """Tags and releases.

    Updates repository with changes and releases package to PyPI for general availability.

    Args:
        mode: release mode
        current_branch: current branch in case the current branch cannot easily
        be determined (e.g. on CI)

    """
    _check_credentials()
    is_new_version, version = version_project(mode)
    logger.info(f"Current version: {version}")
    if not version:
        raise ValueError("Undefined version.")
    if mode == CommitType.DEVELOPMENT:
        return
    _update_documentation()
    _update_repository(mode, is_new_version, version, current_branch)
    if is_new_version:
        _release_to_pypi()


def _get_documentation_config() -> Tuple[Path, str]:
    docs_dir = Path(configuration.get_value(ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH))
    module_to_document = configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)

    return docs_dir, module_to_document


def _update_documentation() -> None:
    """Ensures the documentation is in the correct location for releasing.

    Pdoc nests its docs output in a folder with the module's name.
    This process removes this unwanted folder.
    """
    docs_dir, module_to_document = _get_documentation_config()
    generate_documentation(docs_dir, module_to_document)


def _update_repository(mode: CommitType, is_new_version: bool, version: str, current_branch: Optional[str]) -> None:
    """Update repository with changes that happened."""
    with ProjectTempClone(desired_branch_name=current_branch) as git:
        git.configure_for_github()
        time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        commit_message = f"🚀 releasing version {version} @ {time_str}" if is_new_version else f"📰 Automatic changes ⚙"
        if mode == CommitType.RELEASE:
            _commit_release_changes(git, version, commit_message)
        if is_new_version:
            logger.info(f"Tagging commit")
            git.create_tag(version, message=f"release {version}")
            git.force_push_tag()


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


def _check_credentials() -> None:
    # Checks the GitHub token is defined
    configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    # Checks that twine username is defined
    configuration.get_value(ENVVAR_TWINE_USERNAME)
    # Checks that twine password is defined
    configuration.get_value(ENVVAR_TWINE_PASSWORD)


def _release_to_pypi() -> None:
    logger.info("Releasing to PyPI")
    logger.info("Generating a release package")
    root = configuration.get_value(ConfigurationVariable.PROJECT_ROOT)
    with cd(root):
        subprocess.check_call(
            [
                sys.executable,
                "setup.py",
                "clean",
                "--all",
                "sdist",
                "-d",
                OUTPUT_DIRECTORY,
                "--formats=gztar",
                "bdist_wheel",
                "-d",
                OUTPUT_DIRECTORY,
            ]
        )
        _upload_to_test_pypi()
        _upload_to_pypi()


def _upload_to_pypi() -> None:
    logger.info("Uploading to PyPI")
    subprocess.check_call([sys.executable, "-m", "twine", "upload", f"{OUTPUT_DIRECTORY}/*"])
    logger.info("Success 👍")


def _upload_to_test_pypi() -> None:
    if configuration.get_value_or_default(ConfigurationVariable.IGNORE_PYPI_TEST_UPLOAD, False):
        logger.warning("Not testing package upload on PyPI test (https://test.pypi.org)")
        return
    logger.info("Uploading to test PyPI")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "twine",
            "upload",
            "--repository-url",
            "https://test.pypi.org/legacy/",
            f"{OUTPUT_DIRECTORY}/*",
        ]
    )
    logger.info("Success 👍")


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
