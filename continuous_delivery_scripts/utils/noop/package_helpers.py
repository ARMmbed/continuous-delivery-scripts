#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities for retrieving NoOp's package information."""

import logging

from continuous_delivery_scripts.utils.package_helpers import ProjectMetadata, ProjectMetadataFetcher

logger = logging.getLogger(__name__)


class NoOpProjectMetadataFetcher(ProjectMetadataFetcher):
    """Parser of  package metadata."""

    def __init__(self, package_name: str) -> None:
        """Initialiser."""
        super().__init__(package_name)

    def fetch_project_metadata(self) -> ProjectMetadata:
        """Package metadata."""
        return ProjectMetadata(self._package_name)
