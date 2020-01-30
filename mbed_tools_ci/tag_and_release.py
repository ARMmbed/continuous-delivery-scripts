"""Performs package releasing (part of the CI process)."""
import argparse
import datetime
import logging
import subprocess
import sys
import shutil
from pathlib import Path

from mbed_tools_ci.generate_news import version_project
from mbed_tools_ci.utils.configuration import configuration, \
    ConfigurationVariable
from mbed_tools_ci.utils.definitions import CommitType
from mbed_tools_ci.utils.filesystem_helpers import cd
from mbed_tools_ci.utils.git_helpers import GitWrapper
from mbed_tools_ci.utils.logging import log_exception, set_log_level

ENVVAR_TWINE_USERNAME = 'TWINE_USERNAME'
ENVVAR_TWINE_PASSWORD = 'TWINE_PASSWORD'
OUTPUT_DIRECTORY = 'release-dist'

logger = logging.getLogger(__name__)


def tag_and_release(mode: CommitType) -> None:
    """Tags and releases.

    Updates repository with changes and releases package to PyPI for general availability.

    Args:
        mode: release mode
    """
    _check_credentials()
    is_new_version, version = version_project(mode)
    logger.info(f'Current version: {version}')
    if not version:
        raise ValueError('Undefined version.')
    if mode == CommitType.DEVELOPMENT:
        return
    _update_repository(mode, is_new_version, version)
    if is_new_version:
        _release_to_pypi()


def _remove_old_documentation(git: GitWrapper, docs_dir: Path) -> None:
    """Remove existing docs first to make sure no stale pages left behind."""
    if docs_dir.is_dir():
        shutil.rmtree(str(docs_dir))
        git.add(str(docs_dir))


def _add_new_documentation(
        git: GitWrapper, temp_docs_dir: Path, docs_dir: Path) -> None:
    """Move across documentation from the temporary file and add to git."""
    shutil.move(str(temp_docs_dir), str(docs_dir))
    git.add(str(docs_dir))


def _update_documentation(git: GitWrapper) -> None:
    docs_dir = Path(configuration.get_value(
        ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH
    ))
    # Pdoc nests documentation in a folder with the module's name.
    # Only transfer the contents of this folder.
    temp_docs_dir = Path(
        configuration.get_value(
            ConfigurationVariable.DOCUMENTATION_TEMP_CI_OUTPUT_PATH
        ),
        configuration.get_value(
            ConfigurationVariable.MODULE_TO_DOCUMENT
        )
    )

    _remove_old_documentation(git, docs_dir)
    _add_new_documentation(git, temp_docs_dir, docs_dir)


def _update_repository(mode: CommitType, is_new_version: bool,
                       version: str) -> None:
    git = GitWrapper()
    git.configure_for_github()
    if mode == CommitType.RELEASE:
        _update_documentation(git)
        logger.info(f'Committing release [{version}]...')
        git.add(
            configuration.get_value(ConfigurationVariable.VERSION_FILE_PATH))
        git.add(
            configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH))
        git.add(configuration.get_value(ConfigurationVariable.NEWS_DIR))
        time_str = datetime.datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M")
        commit_message = f':rocket: :newspaper: releasing version {version} @ {time_str}' if is_new_version else f':gear: Automatic changes'
        git.commit(f'{commit_message}\n[skip ci]')
        git.push()
        git.pull()
    if is_new_version:
        logger.info(f'Tagging commit')
        git.create_tag(version, message=f'release {version}')
        git.force_push_tag()


def _check_credentials() -> None:
    # Checks the GitHub token is defined
    configuration.get_value(ConfigurationVariable.GIT_TOKEN)
    # Checks that twine username is defined
    configuration.get_value(ENVVAR_TWINE_USERNAME)
    # Checks that twine password is defined
    configuration.get_value(ENVVAR_TWINE_PASSWORD)


def _release_to_pypi() -> None:
    logger.info('Releasing to PyPI')
    logger.info('Generating a release package')
    root = configuration.get_value(ConfigurationVariable.PROJECT_ROOT)
    with cd(root):
        subprocess.check_call(
            [sys.executable, 'setup.py',
             'clean', '--all',
             'sdist', '-d', OUTPUT_DIRECTORY, '--formats=gztar',
             'bdist_wheel', '-d', OUTPUT_DIRECTORY])
        _upload_to_test_pypi()
        _upload_to_pypi()


def _upload_to_pypi() -> None:
    logger.info('Uploading to PyPI')
    subprocess.check_call(
        [sys.executable, '-m', 'twine', 'upload', f'{OUTPUT_DIRECTORY}/*'])
    logger.info('Success 👍')


def _upload_to_test_pypi() -> None:
    logger.info('Uploading to test PyPI')
    subprocess.check_call(
        [sys.executable, '-m', 'twine', 'upload',
         '--repository-url',
         'https://test.pypi.org/legacy/', f'{OUTPUT_DIRECTORY}/*'])
    logger.info('Success 👍')


def main() -> None:
    """Commands.

    Returns:
        success code (0) if successful; failure code otherwise.
    """
    parser = argparse.ArgumentParser(
        description='Releases the project.')
    parser.add_argument('-t', '--release-type',
                        help='type of release to perform',
                        required=True,
                        type=str, choices=CommitType.choices())
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Verbosity, by default errors are reported.")
    args = parser.parse_args()
    set_log_level(args.verbose)
    try:
        tag_and_release(CommitType.parse(args.release_type))
    except Exception as e:
        log_exception(logger, e)
        sys.exit(1)


if __name__ == '__main__':
    main()
