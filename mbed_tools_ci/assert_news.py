"""Ensures news file are created for all new changes to the project."""
import argparse
import logging
import os
import re
import sys
from typing import List

from mbed_tools_ci.utils.configuration import configuration, \
    ConfigurationVariable
from mbed_tools_ci.utils.git_helpers import GitWrapper
from mbed_tools_ci.utils.logging import log_exception, set_log_level

logger = logging.getLogger(__name__)

VALID_EXTENSIONS = ['misc', 'doc', 'removal', 'bugfix', 'feature', 'major']
NEWS_FILE_NAME_FORMAT = r"^[0-9]+.[a-z]+$"


class NewsFileValidator:
    """Verification of the individual news files: naming, existence, content."""

    def __init__(self, full_path: str) -> None:
        """Creates a new instance of NewsFileValidator.

        Args:
            full_path: the full path to the location of the news files
        """
        self._news_file_path = full_path

    def _verify_news_file_name(self) -> None:
        """Ensures that the news file follows naming rules."""
        basename = str(os.path.basename(self._news_file_path))
        if (not basename) or (not re.search(NEWS_FILE_NAME_FORMAT, basename)):
            raise ValueError(
                f'Incorrect news file name [{basename}]. It must follow the following format: {NEWS_FILE_NAME_FORMAT}'
            )
        for extension in VALID_EXTENSIONS:
            if extension in basename:
                break
        else:
            raise ValueError(
                'News file extension must be one of the following: %s' % (
                    ', '.join(VALID_EXTENSIONS)
                )
            )

    def _verify_news_file_content(self) -> None:
        """Ensures the news file exists and is not empty or longer than one line."""
        if not os.path.exists(self._news_file_path):
            raise FileNotFoundError(self._news_file_path)
        with open(self._news_file_path, 'r') as fh:
            file_content = fh.read()
        if not file_content or len(file_content.strip()) == 0:
            raise ValueError(f'Empty news file `{self._news_file_path}`')
        if len(file_content.splitlines()) > 1:
            raise ValueError('News file must only contain 1-line sentence')

    def verify(self) -> None:
        """Verifies news file follows standards."""
        logger.info('Verifying %s' % self._news_file_path)
        self._verify_news_file_name()
        self._verify_news_file_content()


class NewsFileDiscoverer:
    """Checks that all new PRs comprise a news file and that such files follow the standard."""

    def __init__(self) -> None:
        """Creates an instance of NewsFileDiscoverer.

        Set up the git wrapper and save references to the current and master branches
        """
        self.git = GitWrapper()
        self.current_branch = self.git.get_current_branch()
        self.master_branch = self.git.get_master_branch()

    def find_news_file(self) -> List[str]:
        """Determines a list of all the news files which were added as part of the PR.

        Returns:
             list of introduced news files
        """
        news_dir = configuration.get_value(ConfigurationVariable.NEWS_DIR)
        if not os.path.exists(news_dir):
            NotADirectoryError(
                f'News files directory was not specified and default path `{news_dir}` does not exist'
            )
        logger.info(
            f':: Looking for news files in `{news_dir}` [{self.current_branch}]'
        )
        self.git.checkout(self.current_branch)
        self.git.set_upstream_branch(self.current_branch)
        self.git.pull()
        current_commit = self.git.get_current_commit()
        # Delete `master` as it may already exist and be set to the one of interest (on CircleCI anyway and maybe on other systems)
        if self.git.branch_exists(self.master_branch):
            self.git.delete_branch(self.master_branch)
        self.git.checkout(self.master_branch)
        self.git.set_upstream_branch(self.master_branch)
        self.git.pull()
        master_branch_commit = self.git.get_current_commit()
        self.git.checkout(self.current_branch)
        project_root = configuration.get_value(
            ConfigurationVariable.PROJECT_ROOT)
        news_dir_relative_path = os.path.relpath(news_dir, start=project_root)
        added_news = self.git.get_changes_list(
            self.git.get_branch_point(
                master_branch_commit, current_commit),
            current_commit, change_type='a',
            dir=news_dir_relative_path
        )
        extension_to_exclude = ['.toml', '.rst']
        return [path for path in added_news if
                len([ex for ex in extension_to_exclude if ex in path]) == 0]

    def is_feature_branch(self) -> bool:
        """States whether the current branch contains new features.

        Returns:
            True if current branch is a feature branch; False otherwise.
        """
        return not self.is_special_branch()

    def is_special_branch(self) -> bool:
        """Checks whether current branch is used for the release process.

        Returns:
              True if current branch is a special; False otherwise.
        """
        return (self.current_branch in [self.git.get_master_branch(),
                                        self.git.get_beta_branch()]
                ) or self.git.is_release_branch(self.current_branch)

    def verify(self) -> None:
        """Checks that news files were added in the current branch as part of the PR's changes.

        The files are then individually checked in order to ensure
        they follow the standard in terms of naming and content.

        """
        if not self.is_feature_branch():
            logger.info(
                f'No need for news file on branch [{self.current_branch}]'
            )
            return
        added_news = self.find_news_file()
        news_dir = configuration.get_value(ConfigurationVariable.NEWS_DIR)
        project_root = configuration.get_value(
            ConfigurationVariable.PROJECT_ROOT)
        if not added_news or len(added_news) == 0:
            raise FileNotFoundError(
                f'PR must contain a news file in {news_dir}. See README.md'
            )
        logger.info(
            f'{len(added_news)} new news files found in `{news_dir}`'
        )
        logger.info(':: Checking news files format')
        for news_file in added_news:
            NewsFileValidator(os.path.realpath(
                os.path.join(project_root, news_file))).verify()


def main() -> None:
    """Asserts the new PR comprises at least one news file and it adheres to the required standard.

    An exception is raised if a problem with the news file is found.
    """
    parser = argparse.ArgumentParser(
        description='Publish target data report to AWS.')
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        NewsFileDiscoverer().verify()
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == '__main__':
    main()
