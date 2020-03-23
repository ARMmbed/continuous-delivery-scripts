#
# Copyright (c) 2020, Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Checks if valid news files are created for changes in the project."""
import argparse
import logging
import re
import sys
from typing import List, Union
import pathlib

from mbed_tools_ci_scripts.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci_scripts.utils.git_helpers import ProjectTempClone, LocalProjectRepository, GitWrapper
from mbed_tools_ci_scripts.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)

NEWS_FILE_NAME_REGEX = r"^[0-9]+.(misc|doc|removal|bugfix|feature|major)$"


class NewsFileValidator:
    """Verifies individual news files."""

    def __init__(self, absolute_path: Union[pathlib.Path, str]) -> None:
        """Creates a new instance of NewsFileValidator.

        Args:
            absolute_path: the absolute path to the news file
        """
        self._news_file_path = pathlib.Path(absolute_path)
        self._basename = self._news_file_path.name

    def validate_file_name(self) -> None:
        """Ensures the news file follows the naming rules."""
        if re.match(NEWS_FILE_NAME_REGEX, self._basename) is None:
            raise ValueError(
                f'Incorrect news file name "{self._basename}".'
                f' It doesn\'t match the following regex: "{NEWS_FILE_NAME_REGEX}".'
            )

    def validate_file_contents(self) -> None:
        """Ensures the news file is not empty and not longer than one line."""
        file_content = self._news_file_path.read_text()
        if file_content.strip() == "":
            raise ValueError(f'Empty news file "{self._basename}".')
        if len(file_content.splitlines()) > 1:
            raise ValueError(f'News file "{self._basename}" contains more than one line.')

    def validate(self) -> None:
        """Runs all validators."""
        logger.info(f"Verifying {self._basename}")
        self.validate_file_name()
        self.validate_file_contents()


def validate_news_file(absolute_path: Union[pathlib.Path, str]) -> None:
    """Applies NewsFileValidator validation logic to news file."""
    NewsFileValidator(absolute_path).validate()


def find_news_files(git: GitWrapper, root_dir: str, news_dir: str) -> List[str]:
    """Determines a list of all the news files which were added as part of the PR.

    Args:
        git: Instance of GitWrapper.
        root_dir: Root directory of the project.
        news_dir: Relative path to news directory.

    Returns:
        list: list of absolute paths to news files
    """
    files_changed = git.list_files_added_on_current_branch()
    # Relies on the fact GitWrapper returns paths that are always relative
    # to the project root.
    added_news_files = [file_path for file_path in files_changed if file_path.startswith(news_dir)]
    return [str(pathlib.Path(root_dir, file_path)) for file_path in added_news_files]


def validate_news_files(git: GitWrapper, root_dir: str, news_dir: str) -> None:
    """Checks that news files exist and pass validation checks.

    Args:
        git: Instance of GitWrapper.
        root_dir: Root directory of the project.
        news_dir: Relative path to news directory.
    """
    added_news_files = find_news_files(git=git, news_dir=news_dir, root_dir=root_dir,)
    if not added_news_files:
        raise FileNotFoundError(f"PR must contain a news file in {news_dir}. See README.md.")
    for absolute_file_path in added_news_files:
        validate_news_file(absolute_file_path)


def main() -> None:
    """Asserts the new PR comprises at least one news file and it adheres to the required standard."""
    parser = argparse.ArgumentParser(description="Check correctly formatted news files exist on feature branch.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-b", "--current-branch", help="Name of the current branch", nargs="?")
    group.add_argument("-l", "--local", action="store_true", help="perform checks directly on local repository")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Verbosity, by default errors are reported.",
    )
    args = parser.parse_args()
    set_log_level(args.verbose)

    with (
        LocalProjectRepository()  # type: ignore
        if args.local
        else ProjectTempClone(desired_branch_name=args.current_branch)
    ) as git:
        if git.is_current_branch_feature():
            root_dir = configuration.get_value(ConfigurationVariable.PROJECT_ROOT)
            absolute_news_dir = configuration.get_value(ConfigurationVariable.NEWS_DIR)
            news_dir = str(pathlib.Path(absolute_news_dir).relative_to(root_dir))
            try:
                validate_news_files(
                    git=git, news_dir=news_dir, root_dir=root_dir,
                )
            except Exception as e:
                log_exception(logger, e)
                sys.exit(1)


if __name__ == "__main__":
    main()
