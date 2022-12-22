#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""No Operation plugin."""
import logging
from pathlib import Path
from typing import Optional, Dict

from continuous_delivery_scripts.spdx_report.spdx_project import SpdxProject
from continuous_delivery_scripts.utils.definitions import CommitType
from continuous_delivery_scripts.utils.git_helpers import GitWrapper
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage, get_language_from_file_name

logger = logging.getLogger(__name__)


class NoOp(BaseLanguage):
    """Specific actions for a NoOp project."""

    def get_related_language(self) -> str:
        """Gets the related language."""
        return get_language_from_file_name(__file__)

    def package_software(self, mode: CommitType, version: str) -> None:
        """No Op."""
        pass

    def release_package_to_repository(self, mode: CommitType, version: str) -> None:
        """No Op."""
        pass

    def check_credentials(self) -> None:
        """No Op."""
        pass

    def generate_code_documentation(self, output_directory: Path, module_to_document: str) -> None:
        """No Op."""
        pass

    def can_add_licence_headers(self) -> bool:
        """No Op."""
        return False

    def can_get_project_metadata(self) -> bool:
        """No Op."""
        """States whether project metadata can be retrieved."""
        return False

    def get_current_spdx_project(self) -> Optional[SpdxProject]:
        """No Op."""
        return None

    def tag_release(self, git: GitWrapper, version: str, shortcuts: Dict[str, bool]) -> None:
        """Tags release commit."""
        pass
