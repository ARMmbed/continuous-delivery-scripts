#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Plugin for Docker projects."""
import logging
from pathlib import Path
from typing import Optional

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name

logger = logging.getLogger(__name__)


class Docker(BaseLanguage):
    """Specific actions for a Docker project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def package_software(self, mode: CommitType, version: str) -> None:
        """Todo build docker image."""
        super().package_software(mode, version)

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """Todo push image to repository e.g. ecr, artifactory."""
        super().release_package_to_repository(mode, version)

    def check_credentials(self) -> None:
        """Checks any credentials."""
        super().check_credentials()
        # Todo check ECR or artifactory

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Generates the code documentation."""
        super().generate_code_documentation(output_directory, module_to_document)
        # TODO

    def can_add_licence_headers(self) -> bool:
        """States that licence headers can be added."""
        return True

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return False

    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """Gets current SPDX description."""
        # TODO
        return None
