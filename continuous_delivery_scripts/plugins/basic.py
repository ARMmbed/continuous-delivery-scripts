#
# Copyright (C) 2020-2025 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Basic plugin."""
import logging
from pathlib import Path
from typing import Optional

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name

logger = logging.getLogger(__name__)


class Basic(BaseLanguage):
    """Specific actions for a Basic project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def package_software(self, mode: CommitType, version: str) -> None:
        """Basic."""
        super().package_software(mode, version)

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """Basic."""
        super().release_package_to_repository(mode, version)

    def check_credentials(self) -> None:
        """Basic."""
        super().check_credentials()

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """Basic."""
        super().generate_code_documentation(output_directory, module_to_document)

    def can_add_licence_headers(self) -> bool:
        """Basic."""
        return False

    def can_get_project_metadata(self) -> bool:
        """States whether project metadata can be retrieved."""
        return False

    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """Basic."""
        return None
