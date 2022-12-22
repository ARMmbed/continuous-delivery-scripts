#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Python projects."""
import logging
import shutil
import sys
from pathlib import Path
from subprocess import check_call
from typing import List, Optional

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.filesystem_helpers import TemporaryDirectory
from continuous_delivery_scripts.utils.filesystem_helpers import cd
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name
from continuous_delivery_scripts.utils.logging import log_exception
from continuous_delivery_scripts.utils.python.package_helpers import (
    CurrentPythonProjectMetadataFetcher,
    generate_package_info,
)

ENVVAR_TWINE_USERNAME = "TWINE_USERNAME"
ENVVAR_TWINE_PASSWORD = "TWINE_PASSWORD"
OUTPUT_DIRECTORY = "release-dist"

logger = logging.getLogger(__name__)


def _create_wheel() -> None:
    root = configuration.get_value(ConfigurationVariable.PROJECT_ROOT)
    with cd(root):
        check_call(
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


def _release_to_pypi() -> None:
    logger.info("Releasing to PyPI")
    root = configuration.get_value(ConfigurationVariable.PROJECT_ROOT)
    with cd(root):
        _upload_to_test_pypi()
        _upload_to_pypi()


def _upload_to_pypi() -> None:
    logger.info("Uploading to PyPI")
    check_call([sys.executable, "-m", "twine", "upload", f"{OUTPUT_DIRECTORY}/*"])
    logger.info("Success 👍")


def _upload_to_test_pypi() -> None:
    if configuration.get_value_or_default(ConfigurationVariable.IGNORE_REPOSITORY_TEST_UPLOAD, False):
        logger.warning("Not testing package upload on PyPI test (https://test.pypi.org)")
        return
    logger.info("Uploading to test PyPI")
    check_call(
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


def _generate_pdoc_command_list(output_directory: Path, module: str) -> List[str]:
    return [
        "pdoc",
        "--html",
        f"{module}",
        "--output-dir",
        f"{str(output_directory)}",
        "--force",
        "--config",
        "show_type_annotations=True",
    ]


def _call_pdoc(output_directory: Path, module: str) -> None:
    """Calls Pdoc for generating the docs."""
    logger.info("Creating Pdoc documentation.")
    command_list = _generate_pdoc_command_list(output_directory, module)
    check_call(command_list)


def _generate_pdoc_in_correct_structure(module_to_document: str, output_directory: Path) -> None:
    """Ensures the documentation is in the correct location.

    Pdoc nests its docs output in a folder with the module's name.
    This process removes this unwanted folder.
    """
    with TemporaryDirectory() as temp_dir:
        _call_pdoc(temp_dir, module_to_document)
        docs_contents_dir = temp_dir.joinpath(module_to_document)
        if docs_contents_dir.exists() and docs_contents_dir.is_dir():
            for element in docs_contents_dir.iterdir():
                shutil.move(str(element), str(output_directory))


def _get_current_spdx_project() -> SpdxProject:
    """Gets information about the current project/package."""
    logger.info("Generating package information.")
    try:
        # Trying to generate the egg for the package but this may fail. If so, continue.
        generate_package_info()
    except Exception as e:
        log_exception(logger, e)
    return SpdxProject(CurrentPythonProjectMetadataFetcher())


class Python(BaseLanguage):
    """Specific actions for a Python project."""

    def get_related_language(self) -> str:
        """Gets related language."""
        return get_language_from_file_name(__file__)

    def package_software(self, mode: CommitType, version: str) -> None:
        """Packages the software into a wheel."""
        super().package_software(mode, version)
        _create_wheel()

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """Releases to PyPI."""
        super().release_package_to_repository(mode, version)
        _release_to_pypi()

    def check_credentials(self) -> None:
        """Checks Twine credentials."""
        super().check_credentials()
        # Checks that twine username is defined
        configuration.get_value(ENVVAR_TWINE_USERNAME)
        # Checks that twine password is defined
        configuration.get_value(ENVVAR_TWINE_PASSWORD)

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Generates code documentation."""
        super().generate_code_documentation(output_directory, module_to_document)
        _generate_pdoc_in_correct_structure(module_to_document, output_directory)

    def can_add_licence_headers(self) -> bool:
        """States that licence headers can be added."""
        return True

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return True

    def should_include_spdx_in_package(self) -> bool:
        """States whether the SPDX documents should be included in the package."""
        return True

    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """Gets the current SPDX description."""
        return _get_current_spdx_project()
