#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Base class for all Language plugins."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import GitWrapper

logger = logging.getLogger(__name__)


def get_language_from_file_name(filename: str) -> str:
    """Gets the language from the plugin filename."""
    return Path(filename).resolve().with_suffix("").name


GENERIC_LICENCE_HEADER_TEMPLATE = """Copyright (C) {date} {author} or its affiliates and Contributors. All rights reserved.
SPDX-License-Identifier: {licence_identifier}
"""  # noqa: E501


def _generate_generic_licence_header_template() -> str:
    """Generates the header template which is put at the top of source files."""
    return GENERIC_LICENCE_HEADER_TEMPLATE.format(
        licence_identifier=configuration.get_value(ConfigurationVariable.FILE_LICENCE_IDENTIFIER),
        author="${owner}",
        date="${years}",
    )


class BaseLanguage(ABC):
    """Base class from which language plugins should inherit from.

    To write a new language plugin, implement the following methods at a minimum
    """

    def __str__(self) -> str:
        """String representation."""
        return self.__class__.__name__

    @abstractmethod
    def get_related_language(self) -> str:
        """Gets the name of the corresponding language."""
        pass

    def get_version_tag(self, version: str) -> str:
        """Generates a tag based on the version string."""
        return version

    def generate_source_licence_header_template(self) -> str:
        """Generates the template of the licence header which is put at the top of source files."""
        return _generate_generic_licence_header_template()

    def can_add_licence_headers(self) -> bool:
        """States whether licence headers can be added."""
        return False

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return False

    def should_include_spdx_in_package(self) -> bool:
        """States whether the SPDX documents should be included in the package."""
        return False

    def should_clean_before_packaging(self) -> bool:
        """States whether the repository must be cleaned before packaging happens."""
        return False

    def tag_release(self, git: GitWrapper, version: str, shortcuts: Dict[str, bool]) -> None:
        """Tags release commit."""
        logger.info(f"Tagging commit as release {version}")
        git.create_tag(self.get_version_tag(version), message=f"release {version}")
        for shortcut, version in shortcuts.items():
            if version:
                git.create_tag(self.get_version_tag(shortcut), message=f"{shortcut} release")
            else:
                git.create_tag(shortcut, message=shortcut)

    @abstractmethod
    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Generates the code documentation."""
        logger.info("Generating code documentation")
        pass

    @abstractmethod
    def package_software(self, mode: CommitType, version: str) -> None:
        """Package the software so that it can get released."""
        if mode == CommitType.RELEASE:
            logger.info(f"Generating a release package [{version}]")
        elif mode == CommitType.BETA:
            logger.info(f"Generating a pre-release package [{version}]")
        else:
            logger.info(f"Generating a development package [{version}]")
        pass

    @abstractmethod
    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """Release the package to the official software repository."""
        logger.info(f"Uploading the package [{version}]")
        pass

    @abstractmethod
    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """Gets current project SPDX."""
        pass

    def check_credentials(self) -> None:
        """Checks necessary credentials are set for releasing."""
        # Checks the GitHub token is defined
        configuration.get_value(ConfigurationVariable.GIT_TOKEN)
